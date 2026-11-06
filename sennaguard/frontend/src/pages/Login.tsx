import { useState, type FormEvent } from 'react'
import { Eye, EyeOff, LogIn } from 'lucide-react'
import { useApi } from '../lib/api'
import { useSessao } from '../lib/sessao'
import { Marca } from '../components/Shell'

export default function Login() {
  const { entrar } = useSessao()
  const { dados: pub } = useApi<{ simulacao: boolean; senha_demo: string | null }>('/api/publico')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [ver, setVer] = useState(false)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setErro(''); setEnviando(true)
    try { await entrar(email, senha) } catch (x) { setErro((x as Error).message) } finally { setEnviando(false) }
  }

  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-[380px]">
        <div className="mb-8 flex items-center gap-3">
          <Marca />
          <div className="leading-tight">
            <div className="text-[14px] font-bold tracking-[0.14em]">SENNAGUARD</div>
            <div className="text-[11px] text-tinta-3">NOC Matriz · Filial</div>
          </div>
        </div>

        <form onSubmit={enviar} className="overflow-hidden rounded-2xl border border-fio bg-painel">
          {/* O enlace em miniatura: fibra levando o tráfego, rádio em espera. */}
          <svg className="block h-[18px] w-full" aria-hidden>
            <line x1="0" y1="6" x2="100%" y2="6" stroke="var(--color-fibra)" strokeWidth="2" strokeDasharray="8 4" className="trilho-ativo" />
            <line x1="0" y1="13" x2="100%" y2="13" stroke="var(--color-radio)" strokeOpacity=".4" strokeWidth="2" />
          </svg>
          <div className="flex flex-col gap-4 px-6 pb-6 pt-5">
            <div>
              <h1 className="text-[20px] font-semibold tracking-[-0.02em]">Entrar no NOC</h1>
              <p className="mt-1 text-tinta-3">Use o e-mail cadastrado pela equipe do NOC.</p>
            </div>

            <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">
              E-mail
              <input type="email" required autoFocus autoComplete="username" value={email} onChange={e => setEmail(e.target.value)}
                className="h-10 rounded-lg border border-fio bg-fenda px-3 text-[13px] text-tinta placeholder:text-tinta-4 focus:border-fibra/60 focus:outline-none"
                placeholder="voce@empresa.com.br" />
            </label>
            <label className="flex flex-col gap-1.5 text-[12px] font-medium text-tinta-2">
              Senha
              <span className="relative">
                <input type={ver ? 'text' : 'password'} required autoComplete="current-password" value={senha} onChange={e => setSenha(e.target.value)}
                  className="h-10 w-full rounded-lg border border-fio bg-fenda pl-3 pr-10 text-[13px] text-tinta focus:border-fibra/60 focus:outline-none" />
                <button type="button" onClick={() => setVer(!ver)} aria-label={ver ? 'Esconder senha' : 'Mostrar senha'}
                  className="absolute right-1 top-1 grid size-8 place-items-center rounded-md text-tinta-3 hover:text-tinta">
                  {ver ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </span>
            </label>

            {erro && <p role="alert" className="rounded-lg bg-desastre/10 px-3 py-2 text-[12px] text-desastre">{erro}</p>}

            <button disabled={enviando}
              className="mt-1 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-fibra font-semibold text-rack transition-[background-color,transform] duration-150 hover:bg-fibra-hover active:scale-[0.97] disabled:opacity-50">
              <LogIn className="size-4" />{enviando ? 'Entrando…' : 'Entrar'}
            </button>
          </div>
        </form>

        {pub?.simulacao && (
          <div className="mt-4 rounded-xl border border-dashed border-fio-forte px-4 py-3 text-[12px] leading-relaxed text-tinta-3">
            <b className="font-semibold text-tinta-2">Modo demonstração.</b> Senha <code className="font-mono text-tinta-2">{pub.senha_demo}</code> para
            {' '}<span className="font-mono text-tinta-2">matheus.ziravello@gmail.com</span> (administrador) ou
            {' '}<span className="font-mono text-tinta-2">cliente@filial.local</span> (cliente).
          </div>
        )}
        <p className="mt-6 text-center text-[11px] text-tinta-4">Esqueceu a senha? Peça ao administrador do NOC para redefinir.</p>
      </div>
    </div>
  )
}
