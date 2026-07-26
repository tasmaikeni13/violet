/-
Violet — periodicity.

Two theorems live here, and they are the two halves of the design argument.

*Open loop.*  When both banks are autonomous odometers on coprime moduli the
joint state is a single counter on `ZMod (n^r) × ZMod (m^k)`; its period is
exactly the product of the moduli, and — the point of the cryptanalysis — the
state at time `t` is a *function of `t` alone*.

*Closed loop.*  When the rotor bank is driven by an arbitrary, possibly
message-dependent rule, no counting argument on the rotor bank survives.  The
period floor is recovered from the one component that is still autonomous: the
switch clock.  The theorem below grants the adversary complete control of the
rotor rule and still forbids a state repetition before `K` letters.
-/
import Mathlib.Tactic
import Mathlib.Data.ZMod.Basic

namespace Violet

/-! ### Open loop: a coprime pair of counters -/

section OpenLoop

variable {N K : ℕ}

/-- One tick of the joint odometer. -/
def jointStep (s : ZMod N × ZMod K) : ZMod N × ZMod K := (s.1 + 1, s.2 + 1)

/-- After `t` ticks the joint odometer has added `t` to both counters. -/
theorem jointStep_iterate (s : ZMod N × ZMod K) (t : ℕ) :
    jointStep^[t] s = (s.1 + (t : ZMod N), s.2 + (t : ZMod K)) := by
  induction t with
  | zero => simp
  | succ t ih =>
      rw [Function.iterate_succ_apply', ih]
      simp only [jointStep, Prod.mk.injEq]
      push_cast
      exact ⟨by ring, by ring⟩

/-- The joint odometer returns to its start exactly at the multiples of
`N * K`, provided the moduli are coprime.  This is the exact period of the
open-loop machine. -/
theorem jointStep_fixed_iff [NeZero N] [NeZero K] (h : Nat.Coprime N K)
    (s : ZMod N × ZMod K) (t : ℕ) :
    jointStep^[t] s = s ↔ N * K ∣ t := by
  rw [jointStep_iterate, Prod.ext_iff]
  simp only [add_eq_left]
  rw [ZMod.natCast_eq_zero_iff, ZMod.natCast_eq_zero_iff]
  exact ⟨fun ⟨h1, h2⟩ => Nat.Coprime.mul_dvd_of_dvd_of_dvd h h1 h2,
         fun hd => ⟨dvd_trans (Dvd.intro K rfl) hd, dvd_trans (Dvd.intro_left N rfl) hd⟩⟩

/-- Within one period the open-loop machine never repeats a state: the map
`t ↦ state at time t` is injective on `Finset.range (N * K)`. -/
theorem jointStep_injOn [NeZero N] [NeZero K] (h : Nat.Coprime N K)
    (s : ZMod N × ZMod K) {t t' : ℕ} (ht : t < N * K) (ht' : t' < N * K)
    (heq : jointStep^[t] s = jointStep^[t'] s) : t = t' := by
  wlog hle : t ≤ t' generalizing t t'
  · exact (this ht' ht heq.symm (le_of_not_ge hle)).symm
  have hshift : jointStep^[t' - t] (jointStep^[t] s) = jointStep^[t] s := by
    rw [← Function.iterate_add_apply, Nat.sub_add_cancel hle, ← heq]
  have hdvd : N * K ∣ t' - t := (jointStep_fixed_iff h _ _).1 hshift
  have : t' - t < N * K := lt_of_le_of_lt (Nat.sub_le _ _) ht'
  have := (Nat.eq_zero_of_dvd_of_lt hdvd this)
  omega

/-- **Open-loop transparency.**  The state after `t` letters is determined by `t`
and the initial state alone; the message plays no role.  Every classical attack
on a rotor machine — depth, crib dragging, the bombe — is an exploitation of
this single fact. -/
theorem open_loop_message_independent (s : ZMod N × ZMod K) (t : ℕ) :
    jointStep^[t] s = (s.1 + (t : ZMod N), s.2 + (t : ZMod K)) :=
  jointStep_iterate s t

end OpenLoop

/-! ### Closed loop: a guaranteed period floor under an arbitrary rotor rule -/

section ClosedLoop

variable {P : Type*} {K : ℕ}

/-- The closed-loop trajectory.  `F t p q` is *completely arbitrary*: it may
depend on the time, on the rotor state, on the switch state, on the plaintext,
on the ciphertext, and on any pin pattern.  Only the switch clock is pinned
down, and it is autonomous. -/
def traj (F : ℕ → P × ZMod K → P) : ℕ → P × ZMod K → P × ZMod K
  | 0, s => s
  | t + 1, s => (F t (traj F t s), (traj F t s).2 + 1)

/-- The switch component of the trajectory is the autonomous counter. -/
theorem traj_snd (F : ℕ → P × ZMod K → P) (s : P × ZMod K) (t : ℕ) :
    (traj F t s).2 = s.2 + (t : ZMod K) := by
  induction t with
  | zero => simp [traj]
  | succ t ih => simp only [traj, ih]; push_cast; ring

/-- **Period floor.**  Whatever the rotor bank does — even under adversarial,
message-dependent control — the machine cannot revisit a state in fewer than
`K` letters.  Feedback destroys the counting structure the cryptanalyst needs
without destroying the period guarantee the operator needs. -/
theorem closed_loop_period_floor [NeZero K] (F : ℕ → P × ZMod K → P) (s : P × ZMod K)
    {t t' : ℕ} (ht : t < K) (ht' : t' < K) (heq : traj F t s = traj F t' s) : t = t' := by
  have h2 : (t : ZMod K) = (t' : ZMod K) := by
    have := congrArg Prod.snd heq
    rw [traj_snd, traj_snd] at this
    exact add_left_cancel this
  have h3 := (ZMod.natCast_eq_natCast_iff' t t' K).1 h2
  rwa [Nat.mod_eq_of_lt ht, Nat.mod_eq_of_lt ht'] at h3

/-- The trajectory visits `K` pairwise distinct states in its first `K` steps. -/
theorem closed_loop_distinct [NeZero K] (F : ℕ → P × ZMod K → P) (s : P × ZMod K) :
    Function.Injective (fun t : Fin K => traj F t.val s) := by
  intro a b hab
  exact Fin.ext (closed_loop_period_floor F s a.isLt b.isLt hab)

end ClosedLoop

end Violet
