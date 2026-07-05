import { useRef, useState } from "react"
import { Loader2, Upload } from "lucide-react"

import { Button } from "@edenscale/ui/button"

interface BankStatementDropzoneProps {
  onFile: (file: File) => void
  disabled?: boolean
  isUploading?: boolean
}

/**
 * Drag-and-drop (or click-to-browse) target for a single ISO 20022 XML file.
 *
 * No shared dropzone exists in the design system, so this uses the native
 * DataTransfer API directly, mirroring the hidden-input + button affordance of
 * the document upload dialog for keyboard/click parity.
 */
export function BankStatementDropzone({
  onFile,
  disabled = false,
  isUploading = false,
}: BankStatementDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleFiles(files: FileList | null) {
    const file = files?.[0]
    if (file) onFile(file)
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setIsDragging(false)
        if (!disabled) handleFiles(event.dataTransfer.files)
      }}
      className={[
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-12 text-center transition-colors",
        isDragging
          ? "border-conifer-700 bg-conifer-50"
          : "border-[color:var(--border-hairline)] bg-[color:var(--surface-sunken)]",
        disabled ? "opacity-60" : "",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".xml,application/xml,text/xml"
        className="sr-only"
        disabled={disabled}
        onChange={(event) => {
          handleFiles(event.target.files)
          if (inputRef.current) inputRef.current.value = ""
        }}
      />
      {isUploading ? (
        <Loader2 strokeWidth={1.5} className="size-7 animate-spin text-ink-500" />
      ) : (
        <Upload strokeWidth={1.5} className="size-7 text-ink-500" />
      )}
      <div className="flex flex-col gap-1">
        <p className="font-sans text-[15px] text-ink-900">
          {isUploading
            ? "Reading statement…"
            : "Drag a bank statement here"}
        </p>
        <p className="font-sans text-[12px] text-ink-500">
          ISO 20022 XML (camt.053 / camt.052 / camt.054)
        </p>
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        Choose file
      </Button>
    </div>
  )
}
