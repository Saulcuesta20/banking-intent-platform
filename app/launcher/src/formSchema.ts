import type { FormField, LauncherFlowSummary } from './types'

const loanFields: FormField[] = [
  { name: 'customer_id', label: 'Cliente', type: 'text', placeholder: 'ID o nombre del cliente', required: true },
  { name: 'amount', label: 'Monto', type: 'number', placeholder: '10000', required: true },
  { name: 'term', label: 'Plazo', type: 'select', options: ['12 meses', '24 meses', '36 meses', '48 meses'], required: true },
  { name: 'purpose', label: 'Proposito', type: 'textarea', placeholder: 'Describe el motivo del prestamo' },
]

const paymentFields: FormField[] = [
  { name: 'loan_id', label: 'Prestamo', type: 'text', placeholder: 'Numero de prestamo', required: true },
  { name: 'source_account', label: 'Cuenta origen', type: 'text', placeholder: 'Cuenta origen', required: true },
  { name: 'amount', label: 'Monto de pago', type: 'number', placeholder: '1500', required: true },
  { name: 'payment_date', label: 'Fecha de pago', type: 'date', required: true },
]

const customerFields: FormField[] = [
  { name: 'full_name', label: 'Nombre completo', type: 'text', placeholder: 'Nombre del cliente', required: true },
  { name: 'email', label: 'Email', type: 'text', placeholder: 'cliente@empresa.com', required: true },
  { name: 'phone', label: 'Telefono', type: 'text', placeholder: '+52 ...' },
  { name: 'segment', label: 'Segmento', type: 'select', options: ['Personal', 'PyME', 'Empresarial'], required: true },
]

export function fieldsForFlow(flow?: LauncherFlowSummary | null): FormField[] {
  if (!flow) return []
  const id = flow.flow_id.toLowerCase()
  const name = flow.flow_name.toLowerCase()

  if (id.includes('payment') || name.includes('pago')) return paymentFields
  if (id.includes('customer') || name.includes('cliente')) return customerFields
  return loanFields
}
