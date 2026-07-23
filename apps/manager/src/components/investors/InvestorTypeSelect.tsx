import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@edenscale/ui/select"
import {
  INVESTOR_TYPE_OPTIONS,
  type InvestorType,
} from "@/lib/investorTypes"

/** Radix forbids an empty-string item value, so "not set" needs a sentinel that
 *  never reaches the API. */
const UNSET = "__unset__"

interface InvestorTypeSelectProps {
  id: string
  /** "" means unset — the shape every caller's form state already uses. */
  value: InvestorType | ""
  onValueChange: (value: InvestorType | "") => void
  disabled?: boolean
}

export function InvestorTypeSelect({
  id,
  value,
  onValueChange,
  disabled,
}: InvestorTypeSelectProps) {
  return (
    <Select
      value={value || UNSET}
      onValueChange={(next) =>
        onValueChange(next === UNSET ? "" : (next as InvestorType))
      }
      disabled={disabled}
    >
      <SelectTrigger id={id} className="w-full">
        <SelectValue placeholder="Not set" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={UNSET}>Not set</SelectItem>
        {INVESTOR_TYPE_OPTIONS.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
