/-
Violet — the cascade machine and its correctness.

A cascade machine is a state-indexed family of alphabet permutations together
with a stepping rule.  The stepping rule is allowed to consume a symbol, and the
symbol it consumes is the one the receiver can also compute, so encryption and
decryption traverse the *same* state trajectory even when that trajectory
depends on the message.  This is the abstraction under which both stepping
regimes of Violet — the autonomous odometer regime and the tap-controlled
regime — are simultaneously correct.
-/
import Mathlib.Tactic
import Mathlib.GroupTheory.Perm.Sign

namespace Violet

universe u v

/-- A cascade machine over alphabet `A` with state space `S`.

`enc s` is the permutation applied at state `s`; `next s c` is the successor
state, where `c` is the *feedback symbol*.  The feedback symbol is required to
be a function of the state and the ciphertext letter, which is exactly the
information available to a receiver at the moment it must step. -/
structure Machine (A : Type u) (S : Type v) where
  /-- The permutation applied while in state `s`. -/
  enc : S → Equiv.Perm A
  /-- The state transition, driven by the ciphertext letter emitted. -/
  next : S → A → S

namespace Machine

variable {A : Type u} {S : Type v}

/-- Encrypt a message from a given start state. -/
def encrypt (M : Machine A S) : S → List A → List A
  | _, [] => []
  | s, x :: xs => M.enc s x :: M.encrypt (M.next s (M.enc s x)) xs

/-- Decrypt a message from a given start state. -/
def decrypt (M : Machine A S) : S → List A → List A
  | _, [] => []
  | s, y :: ys => (M.enc s).symm y :: M.decrypt (M.next s y) ys

@[simp] theorem encrypt_nil (M : Machine A S) (s : S) : M.encrypt s [] = [] := rfl

@[simp] theorem encrypt_cons (M : Machine A S) (s : S) (x : A) (xs : List A) :
    M.encrypt s (x :: xs) = M.enc s x :: M.encrypt (M.next s (M.enc s x)) xs := rfl

@[simp] theorem decrypt_nil (M : Machine A S) (s : S) : M.decrypt s [] = [] := rfl

@[simp] theorem decrypt_cons (M : Machine A S) (s : S) (y : A) (ys : List A) :
    M.decrypt s (y :: ys) = (M.enc s).symm y :: M.decrypt (M.next s y) ys := rfl

/-- **Correctness.**  Decryption inverts encryption from the same start state,
for *every* stepping rule — in particular for message-dependent ones. -/
theorem decrypt_encrypt (M : Machine A S) (s : S) (xs : List A) :
    M.decrypt s (M.encrypt s xs) = xs := by
  induction xs generalizing s with
  | nil => simp
  | cons x xs ih => simp [ih]

/-- Encryption preserves message length. -/
theorem length_encrypt (M : Machine A S) (s : S) (xs : List A) :
    (M.encrypt s xs).length = xs.length := by
  induction xs generalizing s with
  | nil => simp
  | cons x xs ih => simp [ih]

/-- Encryption is injective in the message: a cascade machine is a cipher. -/
theorem encrypt_injective (M : Machine A S) (s : S) :
    Function.Injective (M.encrypt s) := by
  intro xs ys h
  have := congrArg (M.decrypt s) h
  rwa [decrypt_encrypt, decrypt_encrypt] at this

/-- The *open-loop* specialisation: the stepping rule ignores the ciphertext, so
the trajectory is a function of time alone. -/
def autonomous (E : S → Equiv.Perm A) (step : S → S) : Machine A S where
  enc := E
  next := fun s _ => step s

@[simp] theorem autonomous_next (E : S → Equiv.Perm A) (step : S → S) (s : S) (c : A) :
    (autonomous E step).next s c = step s := rfl

/-- The state a machine reaches after consuming a message. -/
def runState (M : Machine A S) : S → List A → S
  | s, [] => s
  | s, x :: xs => M.runState (M.next s (M.enc s x)) xs

/-- **Open-loop transparency.**  In the autonomous regime the state after a
message depends only on the message's *length*: it is `step^[t] s`.  Every
classical attack on a rotor machine — depth, crib dragging, the bombe — is an
exploitation of this single fact, and it is exactly what the closed-loop regime
is built to destroy. -/
theorem runState_autonomous (E : S → Equiv.Perm A) (step : S → S) (s : S) (xs : List A) :
    (autonomous E step).runState s xs = step^[xs.length] s := by
  induction xs generalizing s with
  | nil => simp [runState]
  | cons x xs ih => simp [runState, ih, Function.iterate_succ_apply]

/-- Two messages of equal length leave an autonomous machine in the same state:
the machine offers the cryptanalyst *depth*. -/
theorem autonomous_depth (E : S → Equiv.Perm A) (step : S → S) (s : S)
    (xs ys : List A) (h : xs.length = ys.length) :
    (autonomous E step).runState s xs = (autonomous E step).runState s ys := by
  rw [runState_autonomous, runState_autonomous, h]

end Machine

end Violet
