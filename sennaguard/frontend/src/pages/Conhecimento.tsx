import { useState, type FormEvent } from 'react'
import { MagnifyingGlass, PencilSimple, Plus, Sparkle } from '@phosphor-icons/react'
import { api, useApi } from '../lib/api'
import { desde } from '../lib/fmt'
import { useSessao } from '../lib/sessao'
import Modal from '../components/Modal'
import { Botao, Card, Carregando, Vazio } from '../components/ui'

export type Artigo = { id: number; titulo: string; problema: string; causa: string; solucao: string; categoria: string; origem_chamado: number | null; status: 'rascunho' | 'publicado'; autor: string; atualizado_em: number }
const campo = 'w-full rounded-lg border border-fio bg-fenda px-3 text-tinta placeholder:text-tinta-4 focus:border-fibra/60 focus:outline-none'

export default function Conhecimento() {
  const { pode } = useSessao()
  const [q, setQ] = useState('')
  const [busca, setBusca] = useState('')
  const { dados, recarregar } = useApi<Artigo[]>(`/api/conhecimento?q=${encodeURIComponent(busca)}`, 0, ['conhecimento'])
  const [editando, setEditando] = useState<Partial<Artigo> | null>(null)
  const [lendo, setLendo] = useState<Artigo | null>(null)
  const rascunhos = dados?.filter(a => a.status === 'rascunho') ?? []
  const publicados = dados?.filter(a => a.status === 'publicado') ?? []

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-medium tracking-[-0.02em] text-titulo">Base de conhecimento</h1>
          <p className="mt-1 text-tinta-3">Soluções de problemas já resolvidos. Quando alguém abre um chamado parecido, elas aparecem como sugestão.</p>
        </div>
        {pode('editar_conhecimento') && <Botao variante="primario" onClick={() => setEditando({ status: 'rascunho', categoria: 'outro' })}><Plus weight="bold" />Novo artigo</Botao>}
      </div>

      <form onSubmit={(e: FormEvent) => { e.preventDefault(); setBusca(q) }} className="flex gap-2">
        <div className="relative flex-1">
          <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-tinta-3" />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Descreva o problema: ex. internet lenta no caixa" className={`${campo} h-10 pl-9`} />
        </div>
        <Botao type="submit" className="h-10">Buscar</Botao>
      </form>

      {pode('editar_conhecimento') && rascunhos.length > 0 && (
        <Card titulo="Para revisar" extra={<span className="text-[11px] text-tinta-3">rascunhos criados a partir de chamados resolvidos</span>}>
          <ul className="flex flex-col">
            {rascunhos.map(a => (
              <li key={a.id} className="flex items-center gap-3 border-t border-fio py-2.5 first:border-0">
                <Sparkle size={15} weight="fill" className="text-fibra" />
                <div className="min-w-0 flex-1"><div className="truncate font-medium">{a.titulo}</div>
                  <div className="text-[11px] text-tinta-3">{a.origem_chamado ? `do chamado SG-${a.origem_chamado} · ` : ''}por {a.autor} · há {desde(a.atualizado_em)}</div></div>
                <Botao onClick={() => setEditando(a)}><PencilSimple />Revisar e publicar</Botao>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {!dados ? <Carregando /> : !publicados.length ? <Vazio>Nada encontrado{busca ? ` para "${busca}"` : ''}.</Vazio> : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {publicados.map(a => (
            <button key={a.id} onClick={() => setLendo(a)} className="flex flex-col gap-2 rounded-xl border border-fio bg-painel p-5 text-left transition-colors hover:border-fio-forte">
              <span className="font-semibold leading-snug">{a.titulo}</span>
              <span className="line-clamp-3 text-[12.5px] leading-relaxed text-tinta-2">{a.problema}</span>
              <span className="mt-auto pt-2 text-[11px] text-tinta-3">atualizado há {desde(a.atualizado_em)} · {a.autor}</span>
            </button>
          ))}
        </div>
      )}

      <Modal lado aberto={!!lendo} onClose={() => setLendo(null)} titulo={lendo?.titulo}>
        {lendo && (
          <div className="flex flex-col gap-5 leading-relaxed">
            {(['problema', 'causa', 'solucao'] as const).map(k => lendo[k] && (
              <section key={k}><h3 className="mb-1 text-[12px] font-semibold uppercase tracking-[0.06em] text-tinta-3">{k === 'solucao' ? 'Solução' : k === 'causa' ? 'Causa' : 'Problema'}</h3>
                <p className="whitespace-pre-wrap text-tinta-2">{lendo[k]}</p></section>
            ))}
            {pode('editar_conhecimento') && <Botao className="self-start" onClick={() => { setEditando(lendo); setLendo(null) }}><PencilSimple />Editar</Botao>}
          </div>
        )}
      </Modal>

      <Modal aberto={!!editando} onClose={() => setEditando(null)} titulo={editando?.id ? 'Revisar artigo' : 'Novo artigo'}>
        {editando && <Editor a={editando} onFim={() => { setEditando(null); recarregar() }} />}
      </Modal>
    </div>
  )
}

function Editor({ a, onFim }: { a: Partial<Artigo>; onFim: () => void }) {
  const [f, setF] = useState({ titulo: a.titulo ?? '', problema: a.problema ?? '', causa: a.causa ?? '', solucao: a.solucao ?? '', categoria: a.categoria ?? 'outro' })
  const [erro, setErro] = useState('')
  const salvar = async (status: 'rascunho' | 'publicado') => {
    try {
      await api(a.id ? `/api/conhecimento/${a.id}` : '/api/conhecimento', { method: a.id ? 'PUT' : 'POST', body: JSON.stringify({ ...f, status }) })
      onFim()
    } catch (x) { setErro((x as Error).message) }
  }
  const area = (k: 'problema' | 'causa' | 'solucao', rotulo: string) => (
    <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">{rotulo}
      <textarea rows={3} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} className={`${campo} resize-none py-2`} /></label>
  )
  return (
    <form onSubmit={e => { e.preventDefault(); salvar('publicado') }} className="flex flex-col gap-3.5">
      <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">Título
        <input required minLength={4} maxLength={120} value={f.titulo} onChange={e => setF({ ...f, titulo: e.target.value })} className={`${campo} h-9`} /></label>
      {area('problema', 'Problema (como a pessoa descreve)')}
      {area('causa', 'Causa')}
      {area('solucao', 'Solução')}
      {erro && <p className="text-[12px] text-desastre">{erro}</p>}
      <div className="flex justify-end gap-2 border-t border-fio pt-4">
        {a.id && <Botao type="button" variante="perigo" className="mr-auto" onClick={() => confirm('Apagar este artigo?') && api(`/api/conhecimento/${a.id}`, { method: 'DELETE' }).then(onFim)}>Apagar</Botao>}
        <Botao type="button" onClick={() => salvar('rascunho')}>Salvar rascunho</Botao>
        <Botao type="submit" variante="primario">Publicar</Botao>
      </div>
    </form>
  )
}
