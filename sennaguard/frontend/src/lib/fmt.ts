export const hora = (ts: number) => new Date(ts * 1000).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
export const dataHora = (ts: number | string) =>
  new Date(typeof ts === 'number' ? ts * 1000 : ts).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })

export function duracao(seg: number) {
  seg = Math.max(0, Math.round(seg))
  const d = Math.floor(seg / 86400), h = Math.floor((seg % 86400) / 3600), m = Math.floor((seg % 3600) / 60)
  if (d) return `${d}d ${h}h`
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`
  if (m) return `${m}m`
  return `${seg}s`
}

export const desde = (ts: number) => duracao(Date.now() / 1000 - ts)
export const ms = (v: number | null | undefined) => (v == null ? '—' : `${v.toLocaleString('pt-BR', { maximumFractionDigits: v < 10 ? 1 : 0 })} ms`)

/** Severidade do Zabbix → token de cor. */
export const corSev: Record<string, string> = {
  Desastre: 'var(--color-desastre)', Alta: 'var(--color-alta)', 'Média': 'var(--color-media)', Aviso: 'var(--color-aviso)',
}
