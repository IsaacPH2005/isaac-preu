import katex from 'katex'

export type Segment =
  | { type: 'text'; value: string }
  | { type: 'math'; value: string; display: boolean }

/** Busca el delimitador de cierre no escapado a partir de `from`. */
function findClosing(src: string, from: number, delim: string): number {
  let i = from
  while (i < src.length) {
    const idx = src.indexOf(delim, i)
    if (idx === -1) return -1
    // Cuenta barras invertidas previas: un número impar significa que está escapado.
    let backslashes = 0
    for (let j = idx - 1; j >= from && src[j] === '\\'; j--) backslashes++
    if (backslashes % 2 === 0) {
      // Para `$` en línea, no aceptar un `$$` como cierre.
      if (delim === '$' && src[idx + 1] === '$') {
        i = idx + 2
        continue
      }
      return idx
    }
    i = idx + delim.length
  }
  return -1
}

/**
 * Divide un texto mezclado en segmentos de texto y de matemáticas.
 * Soporta $...$, $$...$$, \(...\) y \[...\]. Los delimitadores sin cierre se
 * tratan como texto literal, así que nunca se "rompe" el contenido.
 */
export function splitMath(src: string): Segment[] {
  const out: Segment[] = []
  let buf = ''
  let i = 0
  const flush = () => {
    if (buf) out.push({ type: 'text', value: buf })
    buf = ''
  }

  while (i < src.length) {
    const ch = src[i]
    const next = src[i + 1]

    if (ch === '\\' && next === '$') {
      buf += '$'
      i += 2
      continue
    }

    if (ch === '\\' && (next === '(' || next === '[')) {
      const close = next === '(' ? '\\)' : '\\]'
      const end = src.indexOf(close, i + 2)
      if (end !== -1) {
        flush()
        out.push({ type: 'math', value: src.slice(i + 2, end), display: next === '[' })
        i = end + 2
        continue
      }
    }

    if (ch === '$') {
      const display = next === '$'
      const delim = display ? '$$' : '$'
      const start = i + delim.length
      const end = findClosing(src, start, delim)
      if (end !== -1 && src.slice(start, end).trim()) {
        flush()
        out.push({ type: 'math', value: src.slice(start, end), display })
        i = end + delim.length
        continue
      }
    }

    buf += ch
    i++
  }
  flush()
  return out
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const cache = new Map<string, string>()

export function renderMathHtml(src: string): string {
  if (!src) return ''
  const hit = cache.get(src)
  if (hit !== undefined) return hit

  const html = splitMath(src)
    .map((seg) => {
      if (seg.type === 'text') return escapeHtml(seg.value).replace(/\n/g, '<br>')
      try {
        return katex.renderToString(seg.value, {
          displayMode: seg.display,
          throwOnError: false,
          strict: 'ignore',
          trust: false,
          output: 'html',
        })
      } catch {
        const raw = seg.display ? `$$${seg.value}$$` : `$${seg.value}$`
        return `<code class="math-error">${escapeHtml(raw)}</code>`
      }
    })
    .join('')

  if (cache.size > 2000) cache.clear()
  cache.set(src, html)
  return html
}

/** Versión en texto plano (LaTeX conservado) para copiar al portapapeles. */
export function questionToPlainText(q: { question_number: number; statement: string; options: string[] }): string {
  const header = q.question_number ? `${q.question_number}. ` : ''
  const opts = q.options.length ? `\n\n${q.options.join('\n')}` : ''
  return `${header}${q.statement}${opts}`
}
