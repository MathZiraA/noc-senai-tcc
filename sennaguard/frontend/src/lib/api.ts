import { useCallback, useEffect, useState } from 'react'

export type Enlace = { up: boolean; latencia: number | null; perda: number | null; porta: string; custo: number; ip: string; sinal?: number | null; desde?: number }
export type Visao = {
  modo: string; host: string; atualizado: number; caminho: 'fibra' | 'radio'
  enlaces: { fibra: Enlace; radio: Enlace }
  ultimo_failover: { em: number; segundos: number; retorno_em?: number; retorno_sem_perda?: boolean } | null
  disponibilidade_24h: { fibra: number; radio: number; filial: number } | null
  snmp: { cpu?: number; memoria?: number; uptime?: number; routeros?: string; modelo?: string; disponivel?: boolean }
  internet?: { ativo: 'vivo' | 'tin' | null; vivo: LinkWan; tin: LinkWan } | null
}
export type LinkWan = { up: boolean; latencia: number | null; perda: number | null; ip: string | null }
export type Ponto = { t: number; [serie: string]: number | null }
export type Alerta = {
  id: string; severidade: string; nivel: number; nome: string; host: string
  inicio: number; fim: number | null; ativo: boolean; reconhecido: boolean; chamado: string | null; analise: string | null
  incidente: string; avaliacao: { uteis: number; inuteis: number; meu: boolean | null } | null
}
export type Chamado = {
  numero: string; eventid: string; host: string; nome: string; severidade: string; inicio: string
  status: 'aberto' | 'encerrado'; fim: string; duracao: string
  registros: { seq: number; acao: string; em: string; hash: string }[]
}
export type Integridade = { ok: boolean; registros: number; quebra: number | null; motivo: string }
export type Equipamento = { nome: string; tipo: string; ip: string; modelo: string; local: string; up: boolean; latencia: number | null; sinal?: number | null }
export type Notificacoes = {
  alertas: boolean; chamados_equipe: boolean; desastre: boolean; alta: boolean; media: boolean
  caminho: boolean; chamados: boolean; manutencao: boolean; relatorio: boolean; silencio: boolean
}
export type Painel = { ordem: string[]; ocultos: string[] }
export type Eu = {
  id: number; nome: string; email: string; papel: string; permissoes: string[]; modo: string; telegram: boolean; telegram_disponivel: boolean
  foto: number | null; tour_visto: boolean; painel: Painel | null; notificacoes: Notificacoes
}
export type Usuario = {
  id: number; nome: string; email: string; papel: string; ativo: number
  alerta_email: number; chamado_email: number; criado_em: number; ultimo_acesso: number | null; telegram: number; foto_em: number | null
}

/** Chama a API sob o caminho da aplicação (/sennaguard/api/...). 401 avisa o app para voltar ao login. */
export async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(import.meta.env.BASE_URL + url.replace(/^\//, ''), { headers: { 'Content-Type': 'application/json' }, ...init })
  if (r.status === 401 && !url.startsWith('/api/login')) window.dispatchEvent(new Event('sg:sessao-expirou'))
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `Erro ${r.status}`)
  }
  return r.status === 204 ? (undefined as T) : r.json()
}

/** Envia um arquivo cru no corpo (sem multipart): o servidor confere o tipo pelos primeiros bytes. */
export function enviarArquivo<T>(url: string, arquivo: Blob, metodo = 'POST') {
  return api<T>(url, { method: metodo, body: arquivo, headers: { 'Content-Type': arquivo.type || 'application/octet-stream' } })
}

export const urlFoto = (id: number, versao: number) => `${import.meta.env.BASE_URL}api/usuarios/${id}/foto?v=${versao}`
export const urlAnexo = (id: number) => `${import.meta.env.BASE_URL}api/anexos/${id}`

/** Tempo real: o servidor manda o nome do canal que mudou (visao, alertas, chamados…) e quem usa aquele canal recarrega. */
let fonteEventos: EventSource | null = null
export function iniciarTempoReal() {
  if (fonteEventos) return
  fonteEventos = new EventSource(import.meta.env.BASE_URL + 'api/eventos')
  for (const canal of ['visao', 'alertas', 'chamados', 'manutencao', 'backups', 'testes', 'conhecimento'])
    fonteEventos.addEventListener(canal, () => window.dispatchEvent(new Event(`sg:${canal}`)))
}
export function pararTempoReal() { fonteEventos?.close(); fonteEventos = null }

/** Busca, repete a cada `intervalo` ms (0 = só uma vez) e recarrega na hora quando um dos `canais` muda. */
export function useApi<T>(url: string, intervalo = 0, canais: string[] = []) {
  const [dados, setDados] = useState<T | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const carregar = useCallback(() => {
    if (!url) return // url vazia = o perfil não tem acesso, não busca
    api<T>(url).then(d => { setDados(d); setErro(null) }).catch(e => setErro(e.message))
  }, [url])
  useEffect(() => {
    carregar()
    if (!intervalo) return
    const id = setInterval(carregar, intervalo)
    return () => clearInterval(id)
  }, [carregar, intervalo])
  const chaveCanais = canais.join(',')
  useEffect(() => {
    const lista = chaveCanais ? chaveCanais.split(',') : []
    lista.forEach(c => window.addEventListener(`sg:${c}`, carregar))
    return () => lista.forEach(c => window.removeEventListener(`sg:${c}`, carregar))
  }, [carregar, chaveCanais])
  return { dados, erro, recarregar: carregar }
}

export type Anexo = { id: number; nome: string; tipo: string; tamanho: number }
export type Registro = {
  seq: number; acao: string; autor_nome: string; autor_papel: string; texto: string; em: number; hash: string
  anexos: Anexo[]; visto: { em: number; por: string } | null
}
export type ContextoEnlace = { caminho: 'fibra' | 'radio'; fibra_up: boolean; radio_up: boolean; fibra_ms: string; radio_ms: string }
export type ChamadoManual = {
  id: number; numero: string; titulo: string; descricao: string; categoria: string; impacto: string
  status: 'aberto' | 'em_atendimento' | 'resolvido'; contexto: ContextoEnlace | null
  aberto_por: number; aberto_por_nome: string; responsavel_nome: string | null; criado_em: number; atualizado_em: number
  sla: { resposta: { prazo: number; em: number | null }; solucao: { prazo: number; em: number | null } }
  registros?: Registro[]
}
export type ListaChamados = { chamados: Chamado[]; integridade: Integridade; manuais: ChamadoManual[]; integridade_manuais: Integridade }
