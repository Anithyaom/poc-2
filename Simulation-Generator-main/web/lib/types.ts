// Mirrors backend/src/llm/schemas.py. The parameter/readout `id`s here are the
// shell↔core interface (spec §7) — change these and the prompt together.

export type ParameterType = 'slider' | 'toggle' | 'dropdown' | 'number';

export type ParameterValue = number | boolean | string;

export interface ParameterOption {
  value: string;
  label: string;
}

export interface Parameter {
  id: string;
  label: string;
  type: ParameterType;
  min: number | null;
  max: number | null;
  step: number | null;
  unit: string | null;
  options: ParameterOption[] | null;
  default: ParameterValue;
}

export interface Readout {
  id: string;
  label: string;
  unit: string | null;
}

export interface Manifest {
  title: string;
  concept: string;
  learning_goal: string;
  /** Drives the shell's fixed Step/Run/Pause/Reset bar. Never a per-sim button list. */
  time_stepped: boolean;
  parameters: Parameter[];
  readouts: Readout[];
}

/** Host → core run commands. The shell owns these buttons; the core never draws them. */
export type TransportCommand = 'sim:step' | 'sim:play' | 'sim:pause' | 'sim:reset';

/**
 * One generated simulation. `manifest_json` is stored with the core rather than
 * re-projected from the plan on read: the blueprint can be revised after a
 * simulation exists, and the shell must keep rendering the controls this core was
 * actually built against.
 */
export interface Simulation {
  id: string;
  lab_id: string;
  component_ref: string;
  version: number;
  manifest_json: Manifest;
  core_html: string;
  is_current: boolean;
  change_summary: string | null;
  created_at: string;
}

// --- Simulation blueprint (LLM call #1). Mirrors backend/src/llm/schemas.py. --

export interface PlanParameter extends Parameter {
  rationale: string;
}

export interface SimulationExperience {
  summary: string;
  initial_state: string;
  student_actions: string[];
  completion_state: string;
}

export interface VisualElement {
  name: string;
  description: string;
}

export interface PlanReadout extends Readout {
  description: string;
}

export interface Plan {
  title: string;
  inferred_subject: string;
  inferred_topic: string;
  concept_summary: string;
  learning_objective: string;
  misconception: string;
  simulation_experience: SimulationExperience;
  time_stepped: boolean;
  controls: PlanParameter[];
  visual_elements: VisualElement[];
  readouts: PlanReadout[];
  behavior_rules: string[];
  expected_observations: string[];
}

export interface PlanVersion {
  id: string;
  lab_id: string;
  version: number;
  plan_json: Plan;
  decision: 'pending' | 'accepted' | 'rejected' | 'superseded';
  revision_feedback: string | null;
  created_at: string;
}

export interface Course {
  id: string;
  title: string;
  subject: string;
  created_at: string;
}

export type LabStatus =
  | 'draft'
  | 'plan_review'
  | 'plan_accepted'
  | 'sim_ready'
  | 'refining';

export interface LabSummary {
  id: string;
  title: string;
  audience: string;
  status: LabStatus;
  created_at: string;
}

export interface CourseDetail extends Course {
  labs: LabSummary[];
}

/** Where a lab's textbook section sits in the book (GET /api/labs/:id `source`). */
export interface LabSource {
  ref: string;
  book: string;
  grade: number;
  part: number;
  chapter: number;
  chapter_title: string;
  number: string;
  title: string;
  page_start: number;
  page_end: number;
}

/** GET /api/textbooks — the intake picker's outline. Titles and pages, no text. */
export interface TextbookOutline {
  id: string;
  title: string;
  grade: number;
  source: string;
  chapters: {
    part: number;
    chapter: number;
    title: string;
    sections: { ref: string; number: string; title: string; page_start: number; page_end: number }[];
  }[];
}

export interface Lab {
  id: string;
  course_id: string;
  course_title: string;
  description: string;
  audience: string;
  status: LabStatus;
  title: string;
  /** Optional textbook section the blueprint is grounded in. */
  source_ref: string | null;
  /** `source_ref` resolved; null if there is none or the textbook is not mounted. */
  source: LabSource | null;
  active_plan_id: string | null;
  latest_plan_id: string | null;
  latest_plan_version: number | null;
  latest_plan_json: Plan | null;
  latest_plan_decision: 'pending' | 'accepted' | 'rejected' | 'superseded' | null;
  /** The simulation the workspace renders, if one has been generated. */
  current_simulation_id: string | null;
  created_at: string;
}

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface Job {
  id: string;
  job_type: string;
  status: JobStatus;
  artifact_id: string | null;
  error: string | null;
}
