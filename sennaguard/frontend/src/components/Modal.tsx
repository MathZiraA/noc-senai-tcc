import type { ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

/** Diálogo do Radix: `lado` para detalhes (gaveta à direita), `centro` para formulários. */
export default function Modal({ aberto, onClose, titulo, descricao, lado = false, children }: {
  aberto: boolean; onClose: () => void; titulo: ReactNode; descricao?: ReactNode; lado?: boolean; children: ReactNode
}) {
  return (
    <Dialog.Root open={aberto} onOpenChange={o => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/55 data-[state=open]:animate-[aparece_160ms_ease-out]" />
        <Dialog.Content
          className={`fixed z-50 flex flex-col border border-fio-forte bg-painel shadow-2xl outline-none ${lado
            ? 'inset-y-0 right-0 w-full max-w-[520px] data-[state=open]:animate-[gaveta_240ms_cubic-bezier(0.23,1,0.32,1)]'
            : 'left-1/2 top-1/2 w-[calc(100%-32px)] max-w-[460px] -translate-x-1/2 -translate-y-1/2 rounded-2xl data-[state=open]:animate-[surge_200ms_cubic-bezier(0.23,1,0.32,1)]'}`}>
          <header className="flex items-start justify-between gap-4 border-b border-fio px-6 py-5">
            <div className="min-w-0">
              <Dialog.Title className="text-[16px] font-semibold tracking-[-0.01em]">{titulo}</Dialog.Title>
              {descricao && <Dialog.Description className="mt-1 text-tinta-3">{descricao}</Dialog.Description>}
            </div>
            <Dialog.Close className="-mr-2 grid size-8 shrink-0 place-items-center rounded-lg text-tinta-3 transition-colors hover:bg-painel-alto hover:text-tinta" aria-label="Fechar">
              <X className="size-4" />
            </Dialog.Close>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
