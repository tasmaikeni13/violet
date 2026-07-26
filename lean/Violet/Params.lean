/-
Violet — the concrete machine.

The alphabet has 26 letters and a Strowger bank has 25 levels.  That 26/25 pair
is not decoration: it is the reason the two stages of the cascade cannot fall
into step with each other, and every period statement below is a consequence of
its coprimality.
-/
import Violet.Odometer

namespace Violet

/-- The rotor modulus: the size of the Latin alphabet. -/
def alphaMod : ℕ := 26

/-- The switch modulus: the level count of a Strowger stepping switch. -/
def switchMod : ℕ := 25

theorem coprime_moduli : Nat.Coprime alphaMod switchMod := by decide

/-- Bank moduli inherit coprimality, for every pair of bank sizes. -/
theorem coprime_banks (r k : ℕ) : Nat.Coprime (alphaMod ^ r) (switchMod ^ k) :=
  Nat.Coprime.pow r k coprime_moduli

/-- **Exact open-loop period.**  With `r` rotors and `k` switches the autonomous
machine repeats after exactly `26^r * 25^k` letters and not before. -/
theorem open_loop_exact_period (r k : ℕ)
    [NeZero (alphaMod ^ r)] [NeZero (switchMod ^ k)]
    (s : ZMod (alphaMod ^ r) × ZMod (switchMod ^ k)) (t : ℕ) :
    jointStep^[t] s = s ↔ alphaMod ^ r * switchMod ^ k ∣ t :=
  jointStep_fixed_iff (coprime_banks r k) s t

/-- The period of the two configurations named in the paper, in closed form. -/
theorem strategic_period : alphaMod ^ 14 * switchMod ^ 14 = 650 ^ 14 := by
  unfold alphaMod switchMod
  rw [← Nat.mul_pow]

theorem field_period : alphaMod ^ 8 * switchMod ^ 8 = 650 ^ 8 := by
  unfold alphaMod switchMod
  rw [← Nat.mul_pow]

/-- The strategic configuration exceeds `2^130` states, so its state space alone
puts it past the reach of exhaustive search. -/
theorem strategic_period_gt : 2 ^ 130 < alphaMod ^ 14 * switchMod ^ 14 := by
  rw [strategic_period]
  norm_num

/-- The closed-loop floor of the strategic configuration: even with the rotor
bank under adversarial control, no state recurs inside `25^14 > 2^65` letters. -/
theorem strategic_floor_gt : 2 ^ 65 < switchMod ^ 14 := by
  unfold switchMod
  norm_num

end Violet
