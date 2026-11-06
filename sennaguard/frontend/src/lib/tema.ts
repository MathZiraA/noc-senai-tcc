/** Tema escuro (padrão) ou claro, guardado no navegador de cada pessoa. */
export type Tema = 'escuro' | 'claro'

export function temaAtual(): Tema {
  try { return localStorage.getItem('sg:tema') === 'claro' ? 'claro' : 'escuro' } catch { return 'escuro' }
}

export function aplicarTema(t: Tema = temaAtual()) {
  if (t === 'claro') document.documentElement.dataset.tema = 'claro'
  else delete document.documentElement.dataset.tema
}

export function alternarTema(): Tema {
  const t: Tema = temaAtual() === 'claro' ? 'escuro' : 'claro'
  try { localStorage.setItem('sg:tema', t) } catch { /* sem storage: vale só nesta aba */ }
  aplicarTema(t)
  return t
}
