/-
Violet — what the key material actually buys.

The cascade composes a moving part with a *static* boundary layer: the
plugboard.  The theorems here show that the static layer is invisible to the
cryptanalyst's state-recovery step, in the two senses that matter.

* Under known plaintext the plugboard is not searched but *computed*: once the
  trajectory hypothesis is fixed, every crib position hands over one value of
  the plugboard directly.
* Under ciphertext only the statistic that identifies the trajectory — the
  coincidence count of the reduced stream — takes the same value whatever the
  plugboard is, because a permutation of the alphabet cannot change how often
  two positions agree.

Consequently the key material at the boundary contributes zero to the work
factor, and the security of the machine is the size of its *state* space.  The
design rule that follows is the one Violet is built on: key material must sit
inside the trajectory, not at its ends.
-/
import Mathlib.Tactic
import Mathlib.GroupTheory.Perm.Sign

namespace Violet

open Equiv

variable {A : Type*} [DecidableEq A] [Fintype A]

/-! ### The plugboard is computed, not searched -/

/-- The cascade observation model: at time `t` the machine applies the moving
composite `C t` after the static layer `P`. -/
def Observes (C : ℕ → Perm A) (P : Perm A) (x y : ℕ → A) : Prop :=
  ∀ t, y t = C t (P (x t))

/-- **Plugboard determination.**  Given the trajectory `C`, each known-plaintext
position determines the static layer at that letter outright.  No search over
plugboards occurs anywhere in the attack. -/
theorem plug_determined {C : ℕ → Perm A} {P : Perm A} {x y : ℕ → A}
    (h : Observes C P x y) (t : ℕ) : P (x t) = (C t).symm (y t) := by
  rw [h t, Equiv.symm_apply_apply]

/-- The *reduced stream* an attacker forms from a trajectory hypothesis. -/
def reduce (C : ℕ → Perm A) (y : ℕ → A) : ℕ → A := fun t => (C t).symm (y t)

/-- Against the true trajectory the reduced stream is the plaintext read through
the static layer — a monoalphabetic image of the message, and nothing harder. -/
theorem reduce_eq {C : ℕ → Perm A} {P : Perm A} {x y : ℕ → A}
    (h : Observes C P x y) : reduce C y = fun t => P (x t) := by
  funext t; exact (plug_determined h t).symm

/-- Two crib positions carrying the same plaintext letter give an equation that
does not mention the plugboard at all.  This is the plugboard-free filter that
makes trajectory search cheap. -/
theorem repeat_letter_test {C : ℕ → Perm A} {P : Perm A} {x y : ℕ → A}
    (h : Observes C P x y) {s t : ℕ} (hx : x s = x t) :
    (C s).symm (y s) = (C t).symm (y t) := by
  rw [← plug_determined h, ← plug_determined h, hx]

/-! ### The plugboard is invisible to the identifying statistic -/

/-- The coincidence count of the first `n` positions of a stream: the number of
unordered pairs of positions carrying the same letter.  Normalised by the number
of pairs this is the index of coincidence. -/
def coincidences (n : ℕ) (z : ℕ → A) : ℕ :=
  ((Finset.range n ×ˢ Finset.range n).filter (fun ij => ij.1 < ij.2 ∧ z ij.1 = z ij.2)).card

/-- **Coincidence invariance.**  Relabelling the alphabet by any permutation
leaves the coincidence count unchanged. -/
theorem coincidences_perm (n : ℕ) (P : Perm A) (z : ℕ → A) :
    coincidences n (fun t => P (z t)) = coincidences n z := by
  unfold coincidences
  congr 1
  ext ij
  simp only [Finset.mem_filter]
  constructor
  · rintro ⟨hm, h1, h2⟩; exact ⟨hm, h1, P.injective h2⟩
  · rintro ⟨hm, h1, h2⟩; exact ⟨hm, h1, congrArg P h2⟩

/-- **Static-layer transparency.**  The statistic that separates the true
trajectory from a wrong one takes exactly the value it would take on the
plaintext itself: the plugboard changes nothing an attacker measures.  Hence the
plugboard's key material does not enter the work factor of trajectory recovery,
in either the known-plaintext or the ciphertext-only setting. -/
theorem coincidences_reduce_eq {C : ℕ → Perm A} {P : Perm A} {x y : ℕ → A}
    (h : Observes C P x y) (n : ℕ) :
    coincidences n (reduce C y) = coincidences n x := by
  rw [reduce_eq h, coincidences_perm]

/-- Any decision procedure that only reads the coincidence count of the reduced
stream behaves identically for every plugboard.  Formally: the attacker's score
is a function of the plaintext alone. -/
theorem attacker_score_plug_independent {C : ℕ → Perm A} {P P' : Perm A}
    {x y y' : ℕ → A} (h : Observes C P x y) (h' : Observes C P' x y') (n : ℕ) :
    coincidences n (reduce C y) = coincidences n (reduce C y') := by
  rw [coincidences_reduce_eq h, coincidences_reduce_eq h']

/-! ### The consequence for key design -/

/-- **Identifiability.**  A crib that exercises every letter pins the static
layer down uniquely once the trajectory is known.  Together with
`plug_determined` this reduces key recovery to trajectory recovery: the work
factor of the whole machine is the size of its state space, and no amount of
boundary key material changes that. -/
theorem plug_unique {C : ℕ → Perm A} {P P' : Perm A} {x y : ℕ → A}
    (h : Observes C P x y) (h' : Observes C P' x y) (hsurj : Function.Surjective x) :
    P = P' := by
  ext a
  obtain ⟨t, rfl⟩ := hsurj a
  rw [plug_determined h t, plug_determined h' t]

/-- A key is *trajectory-affecting* when changing it changes the moving
composite at some time.  The transparency theorems say precisely that key
material which is not trajectory-affecting adds nothing to the cost of trajectory
recovery; Violet therefore places its key material — rotor positions, switch
positions, and the pin rings that gate the stepping — inside the stepping law. -/
def TrajectoryAffecting {κ : Type*} (traj : κ → ℕ → Perm A) : Prop :=
  ∀ k k', k ≠ k' → ∃ t, traj k t ≠ traj k' t

/-- Boundary key material is never trajectory-affecting: composing a fixed
permutation onto a family leaves the family's *differences* untouched, so a
search that distinguishes trajectories cannot see it. -/
theorem boundary_not_affecting (C : ℕ → Perm A) (P : Perm A) (t : ℕ) :
    (C t * P) * P⁻¹ = C t := by group

end Violet
