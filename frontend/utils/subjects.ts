const LABELS: Record<string, string> = {
  FISICA: 'Física',
  QUIMICA: 'Química',
  BIOLOGIA: 'Biología',
  ARITMETICA: 'Aritmética',
  ALGEBRA: 'Álgebra',
  GEOMETRIA: 'Geometría',
  TRIGONOMETRIA: 'Trigonometría',
  RAZONAMIENTO_MATEMATICO: 'Raz. Matemático',
  RAZONAMIENTO_VERBAL: 'Raz. Verbal',
  LENGUAJE: 'Lenguaje',
  LITERATURA: 'Literatura',
  HISTORIA: 'Historia',
  GEOGRAFIA: 'Geografía',
  ECONOMIA: 'Economía',
  FILOSOFIA: 'Filosofía',
  PSICOLOGIA: 'Psicología',
  EDUCACION_CIVICA: 'Educación Cívica',
  ANATOMIA: 'Anatomía',
  INGLES: 'Inglés',
  SIN_CLASIFICAR: 'Sin clasificar',
}

// Paleta de tonos por materia (clases completas para que Tailwind las detecte).
const TONES: Record<string, { dot: string; pill: string; active: string }> = {
  FISICA: { dot: 'bg-sky-500', pill: 'bg-sky-50 text-sky-800 ring-1 ring-sky-200', active: 'bg-sky-600 text-white' },
  QUIMICA: { dot: 'bg-violet-500', pill: 'bg-violet-50 text-violet-800 ring-1 ring-violet-200', active: 'bg-violet-600 text-white' },
  BIOLOGIA: { dot: 'bg-emerald-500', pill: 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200', active: 'bg-emerald-600 text-white' },
  ARITMETICA: { dot: 'bg-amber-500', pill: 'bg-amber-50 text-amber-800 ring-1 ring-amber-200', active: 'bg-amber-600 text-white' },
  ALGEBRA: { dot: 'bg-rose-500', pill: 'bg-rose-50 text-rose-800 ring-1 ring-rose-200', active: 'bg-rose-600 text-white' },
  GEOMETRIA: { dot: 'bg-teal-500', pill: 'bg-teal-50 text-teal-800 ring-1 ring-teal-200', active: 'bg-teal-600 text-white' },
  TRIGONOMETRIA: { dot: 'bg-indigo-500', pill: 'bg-indigo-50 text-indigo-800 ring-1 ring-indigo-200', active: 'bg-indigo-600 text-white' },
  RAZONAMIENTO_MATEMATICO: { dot: 'bg-orange-500', pill: 'bg-orange-50 text-orange-800 ring-1 ring-orange-200', active: 'bg-orange-600 text-white' },
}
const FALLBACK = { dot: 'bg-stone-400', pill: 'bg-stone-100 text-stone-700 ring-1 ring-stone-200', active: 'bg-stone-700 text-white' }

export function subjectLabel(subject: string): string {
  if (LABELS[subject]) return LABELS[subject]
  return subject
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function subjectTone(subject: string) {
  return TONES[subject] ?? FALLBACK
}
