import { useEffect, useState } from 'react'
import { ArrowsClockwise, DownloadSimple, Sparkle } from '@phosphor-icons/react'
import { api, useApi } from '../lib/api'
import { dataHora, desde } from '../lib/fmt'
import { Botao, Card, Carregando, Chip, Vazio } from '../components/ui'

type Versao = { arquivo: string; em: number; linhas: number }

export default function Backups() {
  const { dados, recarregar } = useApi<Record<string, Versao[]>>('/api/backups', 0, ['backups'])
  const [host, setHost] = useState('R-FILIAL')
  const [sel, setSel] = useState<[string, string] | null>(null) // [antes, depois]
  const [diff, setDiff] = useState<string[] | null>(null)
  const [explicacao, setExplicacao] = useState('')
  const [ocupado, setOcupado] = useState('')
  const vs = dados?.[host] ?? []

  useEffect(() => { // por padrão compara a versão mais nova com a anterior
    setSel(vs.length > 1 ? [vs[1].arquivo, vs[0].arquivo] : null); setExplicacao('')
  }, [host, dados]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setDiff(null)
    if (sel) api<{ linhas: string[] }>(`/api/backups/${host}/diferenca?a=${sel[0]}&b=${sel[1]}`).then(r => setDiff(r.linhas))
  }, [host, sel])

  const agora = async () => {
    setOcupado('backup')
    try { await api('/api/backups/agora', { method: 'POST' }); recarregar() } finally { setOcupado('') }
  }
  // Baixa a versão como .rsc (o mesmo texto do /export terse, pronto para /import)
  const baixar = async (v: Versao) => {
    const { texto } = await api<{ texto: string }>(`/api/backups/${host}/${v.arquivo}`)
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([texto], { type: 'text/plain' })), download: `${host}-${v.arquivo}` })
    a.click(); URL.revokeObjectURL(a.href)
  }
  const explicar = async () => {
    if (!sel) return
    setOcupado('ia'); setExplicacao('')
    try { setExplicacao((await api<{ texto: string }>(`/api/backups/${host}/explicar?a=${sel[0]}&b=${sel[1]}`, { method: 'POST' })).texto) }
    catch (e) { setExplicacao(`⚠ ${(e as Error).message}`) } finally { setOcupado('') }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-medium tracking-[-0.02em] text-titulo">Backups de configuração</h1>
          <p className="mt-1 text-tinta-3">Exportação diária às 3 h (sem senhas). Uma versão nova só é guardada quando algo muda.</p>
        </div>
        <Botao onClick={agora} disabled={!!ocupado}><ArrowsClockwise className={ocupado === 'backup' ? 'animate-spin' : ''} />Fazer backup agora</Botao>
      </div>

      <div className="grid gap-3 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Card titulo="Versões" acao={<div className="flex gap-1.5">{Object.keys(dados ?? {}).map(h => <Chip key={h} ativo={h === host} onClick={() => setHost(h)}>{h}</Chip>)}</div>}>
          {!dados ? <Carregando /> : !vs.length ? <Vazio>Nenhum backup ainda.</Vazio> : (
            <ul className="flex flex-col gap-1">
              {vs.map((v, i) => {
                const marcado = sel?.includes(v.arquivo)
                return (
                  <li key={v.arquivo} className={`flex items-center rounded-lg transition-colors ${marcado ? 'bg-ativo' : 'hover:bg-pilula-hover'}`}>
                    <button onClick={() => i < vs.length - 1 && setSel([vs[i + 1].arquivo, v.arquivo])}
                      className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2 text-left">
                      <span className={`size-2 rounded-full ${i === 0 ? 'bg-led' : 'bg-tinta-4'}`} />
                      <span className="min-w-0 flex-1">
                        <span className="num block font-medium">{dataHora(v.em)}</span>
                        <span className="text-[11px] text-tinta-3">{i === 0 ? 'atual · ' : ''}há {desde(v.em)} · {v.linhas} linhas</span>
                      </span>
                    </button>
                    <button onClick={() => baixar(v)} title="Baixar .rsc" aria-label={`Baixar a versão de ${dataHora(v.em)}`}
                      className="mr-1.5 grid size-8 shrink-0 place-items-center rounded-md text-tinta-3 transition-colors hover:bg-pilula-hover hover:text-tinta">
                      <DownloadSimple size={16} />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>

        <Card titulo="O que mudou" extra={sel && <span className="num text-[11px] text-tinta-3">{dataHora(vs.find(v => v.arquivo === sel[0])?.em ?? 0)} → {dataHora(vs.find(v => v.arquivo === sel[1])?.em ?? 0)}</span>}
          acao={sel && <Chip onClick={explicar} disabled={!!ocupado}><Sparkle weight="fill" />{ocupado === 'ia' ? 'Analisando…' : 'Explicar com IA'}</Chip>}>
          {explicacao && <div className="mb-4 whitespace-pre-wrap rounded-lg border border-fibra/30 bg-fibra/[0.07] px-4 py-3 leading-relaxed text-tinta-2">{explicacao}</div>}
          {!sel ? <Vazio>Só existe uma versão: ainda não há o que comparar.</Vazio> : !diff ? <Carregando /> : (
            <pre className="max-h-[560px] overflow-auto rounded-lg bg-fenda py-3 font-mono text-[12px] leading-[1.7]">
              {diff.filter(l => !l.startsWith('---') && !l.startsWith('+++')).map((l, i) => (
                <div key={i} className={`px-4 ${l.startsWith('+') ? 'bg-led/10 text-led' : l.startsWith('-') ? 'bg-desastre/10 text-desastre' : l.startsWith('@@') ? 'mt-2 text-tinta-4' : 'text-tinta-3'}`}>{l || ' '}</div>
              ))}
            </pre>
          )}
        </Card>
      </div>

      <Card titulo="Como restaurar um roteador">
        <p className="mb-3 text-tinta-3">O painel só guarda e compara: aplicar é sempre manual, no WinBox. O roteador reinicia e a Filial passa para o rádio (ou fica isolada) até ele voltar.</p>
        <ol className="flex list-decimal flex-col gap-2 pl-5 leading-relaxed text-tinta-2">
          <li><b className="text-tinta">Roteador ainda liga?</b> Prefira o backup completo do próprio roteador (guarda senhas e chaves): WinBox → <i>Files</i> → <code>backup_matriz_…</code> ou <code>backup_filial_…</code> → <i>Restore</i>.</li>
          <li>Se não der (roteador trocado ou zerado): escolha a versão aqui, confira em <i>O que mudou</i> e clique em <DownloadSimple size={13} className="inline" /> para baixar o <code>.rsc</code>.</li>
          <li>No WinBox, arraste o arquivo para <i>Files</i> e rode no terminal: <code>/system reset-configuration no-defaults=yes run-after-reset=NOME-DO-ARQUIVO.rsc</code></li>
          <li>Quando voltar, entre como <code>admin</code> sem senha e recrie o que o arquivo não traz: o usuário administrador com senha nova e os usuários <code>zabbix-ia</code> e <code>sennaguard-teste</code> com as chaves públicas do servidor.</li>
          <li>Clique em <b className="text-tinta">Fazer backup agora</b>: se a configuração voltou igual, nenhuma versão nova aparece.</li>
        </ol>
      </Card>
    </div>
  )
}
