import templateFields from './donor-template-fields.json';

export const CHECKLIST_ROWS = [
  { key: 'education', label: 'Education level' },
  { key: 'college', label: 'University / college' },
  { key: 'nicotine', label: 'Nicotine / tobacco use' },
  { key: 'cannabis', label: 'Cannabis use' },
  { key: 'infectious_disease', label: 'Infectious disease / STI history' },
  { key: 'previous_donation', label: 'Previous donation' },
] as const;

export type DonorQuestionKey = typeof CHECKLIST_ROWS[number]['key'];
export type DonorQuestionAnswers = Record<DonorQuestionKey, string | null>;

export const DONOR_QUESTIONS = CHECKLIST_ROWS.map(row => {
  const field = templateFields.find(field => field.key === row.key);
  if (!field) throw new Error(`Missing donor template field: ${row.key}`);
  return { ...row, question: field.label, options: field.options ?? null };
});

const educationQuestion = DONOR_QUESTIONS.find(field => field.key === 'education');
if (!educationQuestion?.options) throw new Error('Missing donor education options');
export const EDUCATION_OPTIONS = educationQuestion.options;
