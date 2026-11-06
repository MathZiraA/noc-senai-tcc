import { useState, type FormEvent } from 'react'
import { BellRing, Check, Copy, Mail, Pencil, Plus, Trash2, Tv } from 'lucide-react'
import { TelegramLogo } from '@phosphor-icons/react'
import { api, useApi, type Usuario } from '../lib/api'
import { desde } from '../lib/fmt'
import Avatar from '../components/Avatar'
import Modal from '../components/Modal'
import { Botao, Card, Carregando, Chave } from '../components/ui'

const PAPEIS: Record<string, string> = {
  Administrador: 'Gerencia usuários e TVs, aprova testes de failover e atende chamados',
  Analista: 'Investiga incidentes, cuida de backups e manutenções, pede testes de failover',
  Operador: 'Plantão: acompanha o enlace, reconhece alertas e atende chamados',
  Cliente: 'Abre chamados e acompanha o enlace da Filial',
}
const corPapel: Record<string, string> = {
  Administrador: 'var(--color-fibra)', Analista: 'var(--color-radio)', Operador: 'var(--color-tinta-2)', Cliente: 'var(--color-media)',
}
type Form = Omit<Usuario, 'id' | 'criado_em' | 'ultimo_acesso' | 'telegram' | 'foto_em'> & { senha?: string }
const vazio: Form = { nome: '', email: '', papel: 'Operador', ativo: 1, alerta_email: 1, chamado_email: 0, senha: '' }

export default function Usuarios() {
  const { dados, recarregar } = useApi<Usuario[]>('/api/usuarios')
  const [editando, setEditando] = useState<(Form & { id?: number }) | null>(null)
  const [erro, setErro] = useState('')
  if (!dados) return <Carregando />

  const salvar = async (ev: FormEvent) => {
    ev.preventDefault()
    if (!editando) return
    const { id, ...corpo } = editando
    try {
      await api(id ? `/api/usuarios/${id}` : '/api/usuarios', { method: id ? 'PUT' : 'POST', body: JSON.stringify({ ...corpo, senha: corpo.senha || null, ativo: !!corpo.ativo, alerta_email: !!corpo.alerta_email, chamado_email: !!corpo.chamado_email }) })
      setEditando(null); recarregar()
    } catch (e) { setErro((e as Error).message) }
  }
  const remover = async (u: Usuario) => {
    if (!confirm(`Remover ${u.nome}? Essa ação não pode ser desfeita.`)) return
    await api(`/api/usuarios/${u.id}`, { method: 'DELETE' }).catch(e => alert(e.message)); recarregar()
  }
  const abrir = (u?: Usuario) => { setErro(''); setEditando(u ? { ...u, senha: '' } : { ...vazio }) }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px] font-medium tracking-[-0.02em] text-titulo">Usuários</h1>
          <p className="mt-1 text-tinta-3">Quem acessa o NOC e quem recebe os avisos de alerta e de chamado no Telegram.</p>
        </div>
        <Botao variante="primario" onClick={() => abrir()}><Plus />Novo usuário</Botao>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(PAPEIS).map(([papel, desc]) => (
          <div key={papel} className="rounded-xl border border-fio bg-painel px-4 py-3">
            <div className="flex items-baseline justify-between">
              <span className="font-semibold" style={{ color: corPapel[papel] }}>{papel}</span>
              <span className="num text-[18px] font-semibold">{dados.filter(u => u.papel === papel && u.ativo).length}</span>
            </div>
            <div className="mt-1 text-[11px] leading-snug text-tinta-3">{desc}</div>
          </div>
        ))}
      </div>

      {/* Celular: um cartão por pessoa */}
      <ul className="flex flex-col gap-2 md:hidden">
        {dados.map(u => (
          <li key={u.id} className={`flex items-center gap-3 rounded-xl border border-fio bg-painel px-4 py-3 ${u.ativo ? '' : 'opacity-50'}`}>
            <Avatar id={u.id} nome={u.nome} foto={u.foto_em} cor={corPapel[u.papel]} tamanho={38} />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{u.nome}{!u.ativo && <span className="ml-2 text-[11px] text-tinta-3">desativado</span>}</div>
              <div className="truncate text-[11px] text-tinta-3">{u.email}</div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px]">
                <span className="font-medium" style={{ color: corPapel[u.papel] }}>{u.papel}</span>
                <span className="text-tinta-3">· {u.ultimo_acesso ? `entrou há ${desde(u.ultimo_acesso)}` : 'nunca entrou'}</span>
                {!!u.telegram && <TelegramLogo size={13} weight="fill" className="text-[#2aabee]" />}
              </div>
            </div>
            <button onClick={() => abrir(u)} aria-label={`Editar ${u.nome}`} className="grid size-9 place-items-center rounded-lg text-tinta-3 hover:bg-painel-alto hover:text-tinta"><Pencil className="size-4" /></button>
          </li>
        ))}
      </ul>

      <Card className="!p-0 hidden overflow-x-auto md:block">
        <table className="w-full min-w-[760px] text-left">
          <thead className="text-[11px] text-tinta-3">
            <tr className="border-b border-fio">
              <th className="py-3 pl-5 font-medium">Nome</th><th className="font-medium">Papel</th>
              <th className="font-medium">Avisos no Telegram</th><th className="font-medium">Último acesso</th><th className="pr-5" />
            </tr>
          </thead>
          <tbody>
            {dados.map(u => (
              <tr key={u.id} className={`group border-b border-fio last:border-0 ${u.ativo ? '' : 'opacity-50'}`}>
                <td className="py-3 pl-5">
                  <div className="flex items-center gap-3">
                    <Avatar id={u.id} nome={u.nome} foto={u.foto_em} cor={corPapel[u.papel]} />
                    <div><div className="font-medium">{u.nome}{!u.ativo && <span className="ml-2 text-[11px] text-tinta-3">desativado</span>}</div><div className="text-[11px] text-tinta-3">{u.email}</div></div>
                  </div>
                </td>
                <td className="font-medium" style={{ color: corPapel[u.papel] }}>{u.papel}</td>
                <td>
                  <div className="flex gap-1.5 text-[11px]">
                    {!u.telegram && <span className="text-tinta-4" title="Ainda não conectou o Telegram">não conectado</span>}
                    {!!u.telegram && <TelegramLogo size={14} weight="fill" className="text-[#2aabee]" />}
                    {u.alerta_email ? <span className="flex items-center gap-1 rounded-md bg-painel-alto px-1.5 py-0.5 text-tinta-2"><BellRing className="size-3" />Alertas</span> : null}
                    {u.chamado_email ? <span className="flex items-center gap-1 rounded-md bg-painel-alto px-1.5 py-0.5 text-tinta-2"><Mail className="size-3" />Chamados</span> : null}
                    {!u.alerta_email && !u.chamado_email && <span className="text-tinta-4">Nada</span>}
                  </div>
                </td>
                <td className="num text-tinta-2">{u.ultimo_acesso ? `há ${desde(u.ultimo_acesso)}` : <span className="text-tinta-4">Nunca entrou</span>}</td>
                <td className="pr-5">
                  <div className="flex justify-end gap-1 opacity-60 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                    <button onClick={() => abrir(u)} aria-label={`Editar ${u.nome}`} className="grid size-8 place-items-center rounded-lg text-tinta-3 hover:bg-painel-alto hover:text-tinta"><Pencil className="size-3.5" /></button>
                    <button onClick={() => remover(u)} aria-label={`Remover ${u.nome}`} className="grid size-8 place-items-center rounded-lg text-tinta-3 hover:bg-desastre/12 hover:text-desastre"><Trash2 className="size-3.5" /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <TelasTv />

      <Modal aberto={!!editando} onClose={() => setEditando(null)} titulo={editando?.id ? 'Editar usuário' : 'Novo usuário'}>
        {editando && (
          <form onSubmit={salvar} className="flex flex-col gap-3">
            <Campo rotulo="Nome"><input required minLength={2} value={editando.nome} onChange={e => setEditando({ ...editando, nome: e.target.value })} className={campo} /></Campo>
            <Campo rotulo="E-mail"><input required type="email" value={editando.email} onChange={e => setEditando({ ...editando, email: e.target.value })} className={campo} /></Campo>
            <Campo rotulo={editando.id ? 'Nova senha (em branco mantém a atual)' : 'Senha inicial (mínimo 8)'}>
              <input type="password" autoComplete="new-password" required={!editando.id} minLength={8} value={editando.senha ?? ''}
                onChange={e => setEditando({ ...editando, senha: e.target.value })} className={campo} />
            </Campo>
            <fieldset>
              <legend className="mb-1.5 text-[12px] font-medium text-tinta-2">Papel</legend>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(PAPEIS).map(([p, d]) => (
                  <label key={p} className={`cursor-pointer rounded-lg border px-3 py-2 transition-colors ${editando.papel === p ? 'border-fibra/60 bg-fibra/8' : 'border-fio hover:border-fio-forte'}`}>
                    <input type="radio" name="papel" className="sr-only" checked={editando.papel === p} onChange={() => setEditando({ ...editando, papel: p })} />
                    <div className="font-medium">{p}</div><div className="text-[11px] leading-snug text-tinta-3">{d}</div>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="flex flex-col gap-2.5">
              <Chave rotulo="Recebe alertas no Telegram" ligado={!!editando.alerta_email} onChange={v => setEditando({ ...editando, alerta_email: +v })} />
              <Chave rotulo="Recebe chamados novos e respostas no Telegram" ligado={!!editando.chamado_email} onChange={v => setEditando({ ...editando, chamado_email: +v })} />
              <Chave rotulo="Acesso ativo" ligado={!!editando.ativo} onChange={v => setEditando({ ...editando, ativo: +v })} />
            </div>
            {erro && <p className="text-[12px] text-desastre">{erro}</p>}
            <div className="flex justify-end gap-2 border-t border-fio pt-4">
              <Botao type="button" onClick={() => setEditando(null)}>Cancelar</Botao>
              <Botao type="submit" variante="primario">Salvar</Botao>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}

const campo = 'h-9 w-full rounded-lg border border-fio bg-fenda px-3 text-tinta placeholder:text-tinta-4 focus:border-fibra/60 focus:outline-none'

function Campo({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">{rotulo}{children}</label>
}

/** Links fixos da TV do NOC: o link aparece uma vez só, ao ser criado; revogar derruba a tela na hora. */
function TelasTv() {
  const { dados, recarregar } = useApi<{ id: number; nome: string; criado_em: number; criado_por: string; ultimo_uso: number | null }[]>('/api/tv-links')
  const [nome, setNome] = useState('TV do NOC')
  const [novo, setNovo] = useState('')
  const [copiado, setCopiado] = useState(false)
  const criar = async (e: FormEvent) => {
    e.preventDefault()
    const { chave } = await api<{ chave: string }>('/api/tv-links', { method: 'POST', body: JSON.stringify({ nome }) })
    setNovo(`${location.origin}${import.meta.env.BASE_URL}tv#k=${chave}`); setCopiado(false); recarregar()
  }
  return (
    <Card titulo="Telas de TV" extra={<span className="text-[11px] text-tinta-3">link fixo, sem login, só mostra o enlace e os alertas ativos</span>}>
      <form onSubmit={criar} className="flex flex-wrap gap-2">
        <input value={nome} onChange={e => setNome(e.target.value)} required minLength={2} maxLength={60} aria-label="Nome da tela" className={`${campo} max-w-[260px]`} />
        <Botao type="submit" variante="primario"><Tv />Gerar link de TV</Botao>
      </form>
      {novo && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-fibra/40 bg-fibra/10 px-3 py-2.5">
          <code className="min-w-0 flex-1 truncate font-mono text-[12px]">{novo}</code>
          <Botao onClick={() => navigator.clipboard.writeText(novo).then(() => setCopiado(true))}>{copiado ? <Check /> : <Copy />}{copiado ? 'Copiado' : 'Copiar'}</Botao>
          <p className="w-full text-[11px] text-tinta-3">Guarde agora: por segurança, este link não aparece de novo.</p>
        </div>
      )}
      <ul className="mt-4 flex flex-col">
        {dados?.map(t => (
          <li key={t.id} className="flex items-center gap-3 border-t border-fio py-2.5">
            <Tv className="size-4 text-tinta-3" />
            <span className="font-medium">{t.nome}</span>
            <span className="text-[11px] text-tinta-3">criado por {t.criado_por} · {t.ultimo_uso ? `visto há ${desde(t.ultimo_uso)}` : 'nunca aberto'}</span>
            <Botao variante="perigo" className="ml-auto" onClick={() => confirm(`Revogar "${t.nome}"? A TV para de mostrar o painel na hora.`) && api(`/api/tv-links/${t.id}`, { method: 'DELETE' }).then(recarregar)}>Revogar</Botao>
          </li>
        ))}
        {dados && !dados.length && <li className="border-t border-fio pt-3 text-tinta-3">Nenhuma TV conectada.</li>}
      </ul>
    </Card>
  )
}
