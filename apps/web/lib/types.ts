/* Mirrors of the backend Pydantic contracts in
   services/api/app/schemas/production.py. Kept hand-written rather than
   generated so the client can stay a single dependency-free module. */

export type StripColor = "white" | "yellow" | "blue" | "green";
export type RiskLevel = "red" | "amber" | "green";
export type StageStatus = "pending" | "running" | "done" | "failed";
export type ComplianceSeverity = "blocker" | "warning" | "advisory";

export interface Citation {
  url: string;
  title: string;
  excerpt: string;
}

export interface Scene {
  number: string;
  slugline: string;
  interior: "INT" | "EXT" | "INT/EXT";
  location: string;
  time_of_day: string;
  page_start: number;
  eighths: number;
  synopsis: string;
  characters: string[];
  background: string[];
  /** Verbatim scene text, used by the annotated script viewer. */
  raw_text: string;
}

export interface ScriptHeader {
  title: string;
  author: string | null;
  page_count: number;
  scene_count: number;
  format_detected: string;
}

export interface ParsedScript {
  header: ScriptHeader;
  scenes: Scene[];
}

export interface BreakdownElement {
  category: string;
  name: string;
  note: string | null;
  flags_department: boolean;
}

export interface SceneBreakdown {
  scene_number: string;
  elements: BreakdownElement[];
  estimated_setup_hours: number;
}

export interface Breakdown {
  scenes: SceneBreakdown[];
}

export interface ClearanceEntity {
  id: string;
  text: string;
  category: string;
  scene_numbers: string[];
  page_refs: number[];
  context: string;
  portrayal: string;
  is_negative_portrayal: boolean;
}

export interface ClearanceFinding {
  entity_id: string;
  risk: RiskLevel;
  rationale: string;
  real_world_matches: string[];
  citations: Citation[];
  suggested_alternatives: string[];
  searched: boolean;
}

export interface ClearanceReport {
  entities: ClearanceEntity[];
  findings: ClearanceFinding[];
}

export interface LocationIntel {
  location: string;
  jurisdiction: string | null;
  permit_required: boolean;
  permit_cost_note: string | null;
  lead_time_days: number | null;
  weather_window: string | null;
  hazards: string[];
  vendor_notes: string[];
  citations: Citation[];
}

export interface LocationsIntel {
  locations: LocationIntel[];
}

export interface ScheduledScene {
  scene_number: string;
  slugline: string;
  strip_color: StripColor;
  eighths: number;
  location: string;
  cast_ids: string[];
  synopsis: string;
}

export interface ShootDay {
  day_number: number;
  shoot_date: string | null;
  unit: string;
  location: string;
  scenes: ScheduledScene[];
  total_eighths: number;
  company_move: boolean;
  notes: string[];
}

export interface CastMember {
  id: string;
  character: string;
  scene_numbers: string[];
  work_days: number[];
}

export interface Stripboard {
  days: ShootDay[];
  cast: CastMember[];
  company_moves: number;
  shoot_day_count: number;
  rationale: string;
}

export interface ComplianceFlag {
  severity: ComplianceSeverity;
  rule: string;
  day_number: number | null;
  scene_numbers: string[];
  detail: string;
  remedy: string;
}

export interface ComplianceReport {
  flags: ComplianceFlag[];
}

export interface BudgetLine {
  account: string;
  category: string;
  detail: string;
  amount_usd: number;
  driver: string;
}

export interface BudgetTopSheet {
  above_the_line: BudgetLine[];
  below_the_line: BudgetLine[];
  post_and_other: BudgetLine[];
  contingency_pct: number;
  assumptions: string[];
}

export interface CallTime {
  who: string;
  time: string;
  note: string | null;
}

export interface CallSheet {
  day_number: number;
  shoot_date: string | null;
  general_call: string;
  location: string;
  scenes: ScheduledScene[];
  cast_calls: CallTime[];
  department_calls: CallTime[];
  safety_notes: string[];
  weather_note: string | null;
  nearest_hospital: string | null;
}

export interface StageTrace {
  stage: string;
  agent: string;
  crew_role: string;
  status: StageStatus;
  started_at: number | null;
  finished_at: number | null;
  detail: string;
  model: string | null;
  searches: number;
  duration_s?: number | null;
}

export interface ProductionPackage {
  run_id: string;
  script: ParsedScript;
  breakdown: Breakdown;
  clearance: ClearanceReport;
  locations: LocationsIntel;
  stripboard: Stripboard;
  compliance: ComplianceReport;
  budget: BudgetTopSheet;
  call_sheets: CallSheet[];
  trace: StageTrace[];
}

export interface CrewMember {
  stage: string;
  agent: string;
  crew_role: string;
  does: string;
  grounded: boolean;
}

/* Events off the SSE stream. */
export type PipelineEvent =
  | { type: "run_started"; run_id: string; setting: string; parallel_enabled: boolean }
  | { type: "stage"; stage: StageTrace }
  | { type: "complete"; run_id: string; searches_run: number; package: ProductionPackage }
  | { type: "error"; run_id: string; message: string };
