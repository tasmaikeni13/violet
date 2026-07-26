/-
Violet — structural invariants of permutation machines.

A permutation machine is characterised, cryptanalytically, not by how many keys
it has but by *which subset of the symmetric group its encryption permutations
can occupy*.  Three classical machines carry three different proper invariants,
and each invariant is exactly the entry point of the attack that broke the
machine:

* a reflector confines every `E_t` to the conjugacy class of fixed-point-free
  involutions (Enigma);
* a rotor bank alone confines the stage permutation to a single coset of the
  alternating group — its signature cannot move (Hebern, and the rotor half of
  any hybrid);
* a split alphabet confines every `E_t` to the stabiliser of a partition
  (Purple).

The theorems below establish each obstruction and, in the last section, the
escape conditions a cascade must satisfy to carry none of them.
-/
import Mathlib.Tactic
import Mathlib.GroupTheory.Perm.Sign
import Mathlib.GroupTheory.Perm.Support

namespace Violet

open Equiv Equiv.Perm

variable {A : Type*} [DecidableEq A] [Fintype A]

/-! ### The reflector obstruction -/

section Reflector

variable {U : Perm A}

/-- A reflector is an involution of the alphabet without fixed points. -/
structure IsReflector (U : Perm A) : Prop where
  invol : U * U = 1
  derangement : ∀ x, U x ≠ x

/-- Conjugating a reflector yields a reflector.  Since an Enigma-type machine
computes `E_t = g_t * U * g_t⁻¹` for a state-dependent `g_t`, *every* encryption
permutation the machine can ever produce is a reflector. -/
theorem IsReflector.conj (h : IsReflector U) (g : Perm A) :
    IsReflector (g * U * g⁻¹) where
  invol := by
    have hg : g * U * g⁻¹ * (g * U * g⁻¹) = g * (U * U) * g⁻¹ := by group
    rw [hg, h.invol, mul_one, mul_inv_cancel]
  derangement := by
    intro x hx
    apply h.derangement (g⁻¹ x)
    have h1 : (g * U * g⁻¹) x = g (U (g⁻¹ x)) := by simp [Perm.mul_apply]
    rw [h1] at hx
    calc U (g⁻¹ x) = g⁻¹ (g (U (g⁻¹ x))) := by simp
      _ = g⁻¹ x := by rw [hx]

/-- **Self-reciprocity.**  An Enigma-type permutation is its own inverse. -/
theorem reflector_self_inverse (h : IsReflector U) (g : Perm A) :
    (g * U * g⁻¹)⁻¹ = g * U * g⁻¹ :=
  inv_eq_of_mul_eq_one_left (h.conj g).invol

/-- **No letter encrypts to itself.**  This is the property that turned every
crib at Bletchley Park into a filter of strength `(25/26)^L`. -/
theorem reflector_no_self_encryption (h : IsReflector U) (g : Perm A) (x : A) :
    (g * U * g⁻¹) x ≠ x := (h.conj g).derangement x

/-- **The escape criterion.**  A machine that ever produces a permutation with a
fixed point can produce no reflector at that step, hence is not of Enigma type.
A single self-encryption is a complete structural refutation. -/
theorem not_reflector_of_fixed_point (E : Perm A) (x : A) (hx : E x = x) :
    ¬ IsReflector E := fun h => h.derangement x hx

end Reflector

/-! ### The signature obstruction -/

section Signature

/-- The rotor stage: an ordered product of conjugates of fixed wirings, the
conjugating elements being the powers of the alphabet shift that model rotor
displacement. -/
def rotorStage {r : ℕ} (W : Fin r → Perm A) (τ : Perm A) (p : Fin r → ℤ) : Perm A :=
  (List.ofFn fun i => (τ ^ p i)⁻¹ * W i * τ ^ p i).prod

/-- Conjugation cannot move a signature: the target `ℤˣ` is commutative. -/
theorem sign_conj' (g f : Perm A) : Perm.sign (g⁻¹ * f * g) = Perm.sign f := by
  rw [map_mul, map_mul, map_inv,
    mul_comm (Perm.sign g)⁻¹ (Perm.sign f), mul_assoc, inv_mul_cancel, mul_one]

/-- **Signature invariance.**  The signature of the rotor stage does not depend
on the rotor positions: displacement is conjugation, and conjugation cannot move
a signature.  A machine whose only moving part is a rotor bank therefore leaks
one bit for free, at every step, for every key. -/
theorem sign_rotorStage {r : ℕ} (W : Fin r → Perm A) (τ : Perm A) (p : Fin r → ℤ) :
    Perm.sign (rotorStage W τ p) = ∏ i, Perm.sign (W i) := by
  unfold rotorStage
  rw [map_list_prod, List.map_ofFn]
  have hmap : (List.ofFn (Perm.sign ∘ fun i : Fin r => (τ ^ p i)⁻¹ * W i * τ ^ p i))
      = List.ofFn (fun i : Fin r => Perm.sign (W i)) := by
    congr 1
    funext i
    exact sign_conj' _ _
  rw [hmap, List.prod_ofFn]

/-- Two positions of the same rotor bank are never distinguished by signature:
the signature is constant along the whole trajectory. -/
theorem sign_rotorStage_const {r : ℕ} (W : Fin r → Perm A) (τ : Perm A) (p q : Fin r → ℤ) :
    Perm.sign (rotorStage W τ p) = Perm.sign (rotorStage W τ q) := by
  rw [sign_rotorStage, sign_rotorStage]

end Signature

/-! ### The partition obstruction -/

section Partition

variable (B : Set A) [DecidablePred (· ∈ B)]

/-- A permutation *respects* the partition `{B, Bᶜ}` when it maps `B` onto `B`. -/
def RespectsBlock (f : Perm A) : Prop := ∀ x, f x ∈ B ↔ x ∈ B

/-- Block-respecting permutations form a subgroup: a machine whose components
all respect a partition can never leave it, whatever the key. -/
def blockStabilizer : Subgroup (Perm A) where
  carrier := {f | RespectsBlock B f}
  one_mem' := by intro x; simp
  mul_mem' := by
    intro f g hf hg x
    simpa [Perm.mul_apply] using (hf (g x)).trans (hg x)
  inv_mem' := by
    intro f hf x
    have h := hf (f⁻¹ x)
    rw [show f (f⁻¹ x) = x from by simp] at h
    exact h.symm

/-- **The partition obstruction.**  A Purple-type machine cannot send a letter of
one block to a letter of the other — at any time, under any key.  This is a
distinguisher that costs the cryptanalyst nothing and it is what reduced the
Type-B machine to two independent small problems. -/
theorem block_never_crosses {f : Perm A} (hf : RespectsBlock B f) {x : A}
    (hx : x ∈ B) : f x ∈ B := (hf x).2 hx

theorem block_never_crosses' {f : Perm A} (hf : RespectsBlock B f) {x : A}
    (hx : x ∉ B) : f x ∉ B := fun h => hx ((hf x).1 h)

/-- **The escape criterion.**  A single observed transition out of a candidate
block refutes the partition hypothesis for that block. -/
theorem not_respectsBlock (f : Perm A) (x : A) (hx : x ∈ B) (hfx : f x ∉ B) :
    ¬ RespectsBlock B f := fun h => hfx ((h x).2 hx)

end Partition

/-! ### The escape conditions, collected -/

/-- A family of permutations is *invariant-free* when it exhibits, somewhere in
its reachable set, a witness against each of the three classical obstructions:
a fixed point (against the reflector class), two elements of opposite signature
(against the signature coset), and a crossing of every proper nonempty block
(against every partition). -/
structure InvariantFree {ι : Type*} (E : ι → Perm A) : Prop where
  has_fixed_point : ∃ i x, E i x = x
  mixed_signature : ∃ i j, Perm.sign (E i) ≠ Perm.sign (E j)
  crosses_blocks : ∀ (B : Set A) (_ : B.Nonempty) (_ : B ≠ Set.univ),
      ∃ i x, (x ∈ B ∧ E i x ∉ B) ∨ (x ∉ B ∧ E i x ∈ B)

variable {ι : Type*} {E : ι → Perm A}

/-- An invariant-free family contains no reflector, so it is not of Enigma type. -/
theorem InvariantFree.not_all_reflectors (h : InvariantFree E) :
    ¬ ∀ i, IsReflector (E i) := by
  obtain ⟨i, x, hx⟩ := h.has_fixed_point
  intro hall
  exact (hall i).derangement x hx

/-- An invariant-free family is not confined to a signature coset, so it is not
the stage permutation family of any rotor bank. -/
theorem InvariantFree.not_rotor_stage (h : InvariantFree E) {r : ℕ}
    (W : Fin r → Perm A) (τ : Perm A) (p : ι → Fin r → ℤ)
    (hrep : ∀ i, E i = rotorStage W τ (p i)) : False := by
  obtain ⟨i, j, hij⟩ := h.mixed_signature
  exact hij (by rw [hrep i, hrep j, sign_rotorStage_const])

/-- An invariant-free family respects no proper nonempty partition, so it is not
of Purple type. -/
theorem InvariantFree.no_block (h : InvariantFree E) (B : Set A)
    (hne : B.Nonempty) (hproper : B ≠ Set.univ) :
    ¬ ∀ i, RespectsBlock B (E i) := by
  intro hall
  obtain ⟨i, x, hx⟩ := h.crosses_blocks B hne hproper
  rcases hx with ⟨hxB, hEx⟩ | ⟨hxB, hEx⟩
  · exact hEx ((hall i x).2 hxB)
  · exact hxB ((hall i x).1 hEx)

end Violet
