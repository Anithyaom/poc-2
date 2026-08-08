# Interactive Visualization Tools — Prompt Section (README)

> **Purpose:** This section is embedded in a plan-generation prompt. When generating a lesson/teaching plan for Vector Spaces (IIT Roorkee syllabus), select and integrate tools from the catalog below. Each tool maps a core concept to a hands-on, browser-based interactive.

## Instructions for the Plan Generator

1. For each topic in the plan, recommend the most relevant tool(s) from the catalog.
2. State the concept the tool teaches, how the student interacts with it, and its syllabus link.
3. Where noted, include the real-world engineering hook (vibration analysis, structural modes, resonance).
4. All tools are client-side only (no backend). Suggested stack: **Three.js** (3D), **p5.js** (2D/3D interactivity), or plain **HTML5 Canvas + JS**.

## Tool Catalog

### 1. Subspace Detector
- **Concept:** When is a set a subspace?
- **Interaction:** Drag 2–3 vectors in 2D/3D. Tool instantly shows ✅ subspace check (closure under addition/scalar multiplication) and 📐 why (visualizes linear dependence, origin inclusion).
- **Syllabus link:** Unit 3 — Vector Spaces.
- **Starter code:**
```html
<!-- Simple 2D subspace detector -->
<canvas id="subspaceCanvas" width="400" height="400"></canvas>
<script>
  const canvas = document.getElementById('subspaceCanvas');
  const ctx = canvas.getContext('2d');
  // ... (drag vectors, show subspace check)
</script>
```

### 2. Basis Explorer
- **Concept:** How basis vectors span a space.
- **Interaction:** Adjust 2–3 vectors in 2D/3D. Tool draws the span (shaded area), shows linear independence (non-colinearity), auto-updates dimension.
- **Syllabus link:** Critical for diagonalization of symmetric matrices.
- **Hook:** Why basis matters for vibration analysis (modes of oscillation).

### 3. Orthogonal Projection Simulator
- **Concept:** Projection of a vector onto a subspace.
- **Interaction:** Drag vector **v** and orthogonal basis {u₁, u₂}; see real-time projection `proj_u(v) = (v·u₁)u₁ + (v·u₂)u₂`.
- **Syllabus link:** Orthogonal sets (Unit 3).
- **Hook:** "Why do bridges vibrate at specific frequencies? (Projection = resonance)."

### 4. Linear Independence Tester
- **Concept:** When vectors are linearly independent.
- **Interaction:** Input 3 vectors in 3D. Tool computes determinant in real time, shows span (dependent vectors collapse to line/point), visualizes null space.
- **Syllabus link:** Solving vibration systems (3D structural modes).

### 5. Span Visualization Tool
- **Concept:** What is the span of a set of vectors?
- **Interaction:** Add vectors via drag-and-drop; span (shaded region) expands dynamically; checks origin inclusion (subspace requirement).
- **Syllabus link:** Builds intuition for why symmetric matrices need orthogonal bases.

### 6. Dimension Slider
- **Concept:** How dimension changes with vectors.
- **Interaction:** Add vectors (1D → 3D); dimension counter updates (1 → 2 → 3); span shrinks/grows (e.g., 2 vectors → plane).
- **Syllabus link:** Dimension (Unit 3); vibration analysis (2D vibrations = plane).

### 7. Orthogonal Basis Generator
- **Concept:** Generating orthogonal bases from arbitrary vectors.
- **Interaction:** Input 3 vectors → click "Orthogonalize" → tool runs Gram-Schmidt, shows orthogonal basis with error margins.
- **Syllabus link:** Prepares for diagonalization of symmetric matrices (Unit 2).

### 8. Subspace Intersection Explorer
- **Concept:** Intersection of subspaces.
- **Interaction:** Drag 2 subspaces (e.g., planes in 3D); see intersection (line/point); verify `dim(A) + dim(B) = dim(A∩B) + dim(A+B)`.
- **Hook:** Modeling joint vibrations in structures.

### 9. Vibration Mode Simulator
- **Concept:** Vector spaces in engineering vibrations.
- **Interaction:** Adjust mass-spring parameters; see eigenvalues (vibration frequencies); visualize eigenvectors (modes of oscillation).
- **Syllabus link:** Most critical — connects vector spaces to real-world vibrations.

### 10. Orthogonal Complement Builder
- **Concept:** What is the orthogonal complement?
- **Interaction:** Define a subspace (e.g., a plane) → click "Find Complement" → tool shows orthogonal vectors and visualizes decomposition `v = v₁ + v₂`.

## Implementation Notes (for generated plans)

- **Free tools:** Three.js (3D visuals), p5.js (simple 2D/3D interactivity).
- **No backend needed** — everything runs client-side.
- Each generated plan should specify: tool name, target concept, interaction steps, syllabus unit, and (if applicable) the engineering hook.
