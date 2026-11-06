import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronDown, Plus, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useApi, type ChamadoManual, type ListaChamados } from '../lib/api'
import { dataHora, desde } from '../lib/fmt'
import { useSessao } from '../lib/sessao'
import { TrilhoMini } from '../components/Trilho'
import { CATEGORIAS, DetalheChamado, IMPACTOS, NovoChamado, SlaChip, StatusChamado } from '../components/Atendimento'
import Modal from '../components/Modal'
import { Botao, Card, Carregando, Led, Sev, Vazio } from '../components/ui'

export default function Chamados() {
  const { dados, recarregar } = useApi<ListaChamados>('/api/chamados', 60000, ['chamados'])
  const { pode, eu } = useSessao()
  const [params, setParams] = useSearchParams()
  const [aberto, setAberto] = useState<string | null>(null)
  if (!dados) return <Carregando />
  const { chamados, manuais } = dados
  const ig = dados.integridade.ok ? dados.integridade_manuais : dados.integridade
  const registros = dados.integridade.registros + dados.integridade_manuais.registros
  const pendentes = manuais.filter(c => c.status !== 'resolvido').length + chamados.filter(c => c.status === 'aberto').length
  const sel = params.get('sg')
  const cliente = eu?.papel === 'Cliente'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-medium tracking-[-0.02em] text-titulo">Chamados</h1>
          <p className="mt-1 text-tinta-3">{cliente
            ? 'Abra um chamado quando algo não estiver funcionando na Filial e acompanhe o atendimento aqui.'
            : 'Chamados abertos pelas pessoas (SG-xxx) e os automáticos de quedas acima de 1 h (NOC-xxx).'}</p>
        </div>
        {pode('abrir_chamado') && <Botao variante="primario" onClick={() => setParams({ sg: 'novo' })}><Plus />Abrir chamado</Botao>}
      </div>

      <div className={`flex flex-wrap items-center gap-4 rounded-2xl border px-5 py-4 ${ig.ok ? 'border-led/25 bg-led/[0.06]' : 'border-desastre/40 bg-desastre/10'}`}>
        {ig.ok ? <ShieldCheck className="size-6 text-led" strokeWidth={1.7} /> : <ShieldAlert className="size-6 text-desastre" strokeWidth={1.7} />}
        <div>
          <div className="font-semibold">{ig.ok ? 'Histórico íntegro' : `Histórico adulterado no registro ${ig.quebra}`}</div>
          <div className="text-[12px] text-tinta-3">
            {ig.ok ? `${registros} registros, cadeia SHA-256 conferida do primeiro ao último.` : `${ig.motivo}. Os registros a partir dele não têm valor de prova.`}
          </div>
        </div>
        <div className="num ml-auto flex gap-6 text-right">
          <div><div className="text-[22px] font-semibold leading-none">{pendentes}</div><div className="mt-1 text-[11px] text-tinta-3">em andamento</div></div>
          <div><div className="text-[22px] font-semibold leading-none text-tinta-2">{manuais.length + chamados.length - pendentes}</div><div className="mt-1 text-[11px] text-tinta-3">resolvidos</div></div>
        </div>
      </div>

      <h2 className="mt-2 text-[13px] font-semibold text-tinta-2">{cliente ? 'Seus chamados' : 'Abertos pelas pessoas'}</h2>
      {manuais.length === 0 ? <Vazio>Nenhum chamado aberto até agora.</Vazio> : (
        <Card className="!p-0 md:overflow-x-auto">
          <ul>
            {manuais.map(c => <LinhaManual key={c.id} c={c} onAbrir={() => setParams({ sg: String(c.id) })} />)}
          </ul>
        </Card>
      )}

      <h2 className="mt-2 text-[13px] font-semibold text-tinta-2">Automáticos: quedas acima de 1 h</h2>
      <Modal lado={sel !== 'novo'} aberto={!!sel} onClose={() => setParams({})}
        titulo={sel === 'novo' ? 'Abrir chamado' : manuais.find(c => String(c.id) === sel)?.titulo ?? 'Chamado'}
        descricao={sel === 'novo' ? 'A equipe do NOC recebe na hora.' : `SG-${sel}`}>
        {sel === 'novo'
          ? <NovoChamado onCancelar={() => setParams({})} onCriado={c => { recarregar(); setParams({ sg: String(c.id) }) }} />
          : sel && <DetalheChamado id={Number(sel)} onMudou={recarregar} />}
      </Modal>

      {chamados.length === 0 ? <Vazio>Nenhum chamado. Quedas curtas (menos de 1 h) não geram chamado.</Vazio> : (
        <Card className="!p-0 md:overflow-x-auto">
          <ul>
            {chamados.map(c => {
              const exp = aberto === c.numero
              return (
                <li key={c.numero} className="border-b border-fio last:border-0">
                  <button onClick={() => setAberto(exp ? null : c.numero)} aria-expanded={exp}
                    className="grid w-full grid-cols-[minmax(0,1fr)_20px] items-center gap-x-4 gap-y-2 px-4 py-3.5 text-left transition-colors hover:bg-white/[0.02] md:min-w-[720px] md:grid-cols-[120px_minmax(0,1fr)_auto_150px_20px] md:px-5">
                    <span className="font-mono text-[12px] font-medium text-fibra max-md:col-span-2">{c.numero}</span>
                    <span className="flex min-w-0 items-center gap-3 max-md:col-start-1">
                      <TrilhoMini nome={c.nome} />
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{c.nome}</span>
                        <span className="num text-[11px] text-tinta-3">aberto em {dataHora(c.inicio)}</span>
                      </span>
                    </span>
                    <span className="max-md:hidden"><Sev nome={c.severidade} /></span>
                    <span className="num text-[12px] max-md:col-start-1 max-md:row-start-3">
                      {c.status === 'aberto'
                        ? <span className="flex items-center gap-1.5 font-medium"><Led cor="var(--color-media)" pulsa />Aberto há {desde(new Date(c.inicio).getTime() / 1000)}</span>
                        : <span className="text-tinta-3">Encerrado · {c.duracao}</span>}
                    </span>
                    <ChevronDown className={`size-4 text-tinta-3 transition-transform duration-200 max-md:col-start-2 max-md:row-start-2 ${exp ? 'rotate-180' : ''}`} />
                  </button>
                  {exp && (
                    <ol className="mx-4 mb-4 flex flex-col gap-2 overflow-x-auto rounded-xl border border-fio bg-fenda p-4 md:mx-5">
                      {c.registros.map(r => (
                        <li key={r.seq} className="grid min-w-[480px] grid-cols-[48px_110px_120px_minmax(0,1fr)] items-baseline gap-3 text-[12px]">
                          <span className="num font-mono text-tinta-4">#{r.seq}</span>
                          <span className="font-medium capitalize">{r.acao}</span>
                          <span className="num text-tinta-3">{dataHora(r.em)}</span>
                          <span className="truncate font-mono text-[11px] text-tinta-3" title={r.hash}>sha256 {r.hash}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </div>
  )
}

function LinhaManual({ c, onAbrir }: { c: ChamadoManual; onAbrir: () => void }) {
  return (
    <li className="border-b border-fio last:border-0">
      {/* Celular: cartão empilhado */}
      <button onClick={onAbrir} className="flex w-full flex-col gap-1.5 px-4 py-3.5 text-left md:hidden">
        <span className="flex items-center gap-2">
          <span className="font-mono text-[12px] font-medium text-media">{c.numero}</span>
          <span className="ml-auto"><StatusChamado status={c.status} /></span>
        </span>
        <span className="font-medium leading-snug">{c.titulo}</span>
        <span className="text-[11px] text-tinta-3">{CATEGORIAS[c.categoria]} · {IMPACTOS[c.impacto].toLowerCase()} · {c.aberto_por_nome}</span>
        <SlaChip c={c} />
      </button>
      <button onClick={onAbrir} className="hidden w-full min-w-[720px] grid-cols-[100px_minmax(0,1fr)_140px_190px] items-center gap-4 px-5 py-3.5 text-left transition-colors hover:bg-white/[0.02] md:grid">
        <span className="font-mono text-[12px] font-medium text-media">{c.numero}</span>
        <span className="min-w-0">
          <span className="block truncate font-medium">{c.titulo}</span>
          <span className="text-[11px] text-tinta-3">{CATEGORIAS[c.categoria]} · {IMPACTOS[c.impacto].toLowerCase()} · {c.aberto_por_nome}</span>
        </span>
        <StatusChamado status={c.status} />
        <span className="text-right"><SlaChip c={c} /></span>
      </button>
    </li>
  )
}
