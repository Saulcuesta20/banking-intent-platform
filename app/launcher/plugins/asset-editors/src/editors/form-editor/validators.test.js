import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultForm,
  formDefinitionZodSchema,
  normalizeFormField,
  normalizeFormDefinition,
  validateFormDocument,
} from './helpers.js'

test('normalizeFormDefinition keeps contract fields aligned', () => {
  const definition = normalizeFormDefinition({
    form_id: 'form.lending.apply',
    module_id: 'module.lending',
    fields: [
      { field_id: 'f1', name: 'amount', type: 'number', required: true },
      { field_id: 'f2', name: 'term', type: 'number', required: false },
    ],
    layout: 'single-column',
    validation: 'amount > 0',
  })

  assert.equal(definition.form_id, 'form.lending.apply')
  assert.equal(definition.module_id, 'module.lending')
  assert.equal(definition.fields.length, 2)
  assert.equal(definition.fields[0].field_id, 'f1')
  assert.equal(definition.fields[0].name, 'amount')
  assert.equal(definition.fields[0].type, 'number')
  assert.equal(definition.fields[0].required, true)
  assert.equal(definition.fields[1].field_id, 'f2')
  assert.equal(definition.fields[1].required, false)
  assert.equal(definition.layout, 'single-column')
  assert.equal(definition.validation, 'amount > 0')
})

test('validateFormDocument accepts a valid form', () => {
  const result = validateFormDocument({
    payload: {
      form_id: 'form.lending.apply',
      module_id: 'module.lending',
      fields: [
        { field_id: 'f1', name: 'amount', type: 'number', required: true },
      ],
      layout: 'single-column',
      validation: 'amount > 0',
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateFormDocument flags missing required fields', () => {
  const result = validateFormDocument({
    payload: {
      form_id: '',
      module_id: '',
      fields: [],
      layout: '',
      validation: '',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('form_id')))
  assert.ok(result.errors.some((error) => error.includes('module_id')))
})

test('validateFormDocument warns about empty fields', () => {
  const result = validateFormDocument({
    payload: {
      form_id: 'form.lending.apply',
      module_id: 'module.lending',
      fields: [],
      layout: 'single-column',
      validation: '',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('fields')))
})

test('validateFormDocument warns about missing layout', () => {
  const result = validateFormDocument({
    payload: {
      form_id: 'form.lending.apply',
      module_id: 'module.lending',
      fields: [{ field_id: 'f1', name: 'amount', type: 'number', required: true }],
      layout: '',
      validation: '',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('layout')))
})

test('validateFormDocument warns about form_id without dot prefix', () => {
  const result = validateFormDocument({
    payload: {
      form_id: 'form-lending-apply',
      module_id: 'module.lending',
      fields: [{ field_id: 'f1', name: 'amount', type: 'number', required: true }],
      layout: 'single-column',
      validation: '',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('form_id')))
})

test('normalizeFormField normalizes correctly', () => {
  const field = normalizeFormField({
    field_id: 'f1',
    name: 'amount',
    type: 'number',
    required: true,
  })

  assert.equal(field.field_id, 'f1')
  assert.equal(field.name, 'amount')
  assert.equal(field.type, 'number')
  assert.equal(field.required, true)
})

test('createDefaultForm creates valid shape', () => {
  const item = createDefaultForm()
  assert.equal(item.form_id, 'form-new')
  assert.equal(item.module_id, '')
  assert.deepEqual(item.fields, [])
  assert.equal(item.layout, '')
  assert.equal(item.validation, '')
})
