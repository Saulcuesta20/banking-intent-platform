import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createDefaultQaDefinition,
  qaDefinitionZodSchema,
  normalizeQaDefinition,
  validateQaDocument,
} from './helpers.js'

test('normalizeQaDefinition keeps contract fields aligned', () => {
  const definition = normalizeQaDefinition({
    question: 'How do I apply for a loan?',
    answer: 'You can apply online through our mobile app.',
    intent: 'loan.apply',
    source: 'knowledge-base/loan-faq',
    citations: ['https://example.com/loan', 'https://example.com/faq'],
  })

  assert.equal(definition.question, 'How do I apply for a loan?')
  assert.equal(definition.answer, 'You can apply online through our mobile app.')
  assert.equal(definition.intent, 'loan.apply')
  assert.equal(definition.source, 'knowledge-base/loan-faq')
  assert.equal(definition.citations.length, 2)
})

test('validateQaDocument accepts a valid qa', () => {
  const result = validateQaDocument({
    payload: {
      question: 'What is my balance?',
      answer: 'Check your account dashboard.',
      intent: 'balance.check',
      source: 'faq',
      citations: ['https://example.com'],
    },
  })

  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
})

test('validateQaDocument flags missing question and answer', () => {
  const result = validateQaDocument({
    payload: {
      question: '',
      answer: '',
      intent: '',
      source: '',
    },
  })

  assert.equal(result.valid, false)
  assert.ok(result.errors.some((error) => error.includes('question')))
  assert.ok(result.errors.some((error) => error.includes('answer')))
})

test('validateQaDocument warns about missing intent', () => {
  const result = validateQaDocument({
    payload: {
      question: 'How do I check my balance?',
      answer: 'Visit the dashboard.',
      intent: '',
      source: '',
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('intent')))
})

test('validateQaDocument warns about missing citations', () => {
  const result = validateQaDocument({
    payload: {
      question: 'How do I check my balance?',
      answer: 'Visit the dashboard.',
      intent: 'balance.check',
      source: 'faq',
      citations: [],
    },
  })

  assert.ok(result.warnings.some((warning) => warning.includes('citations')))
})

test('createDefaultQaDefinition creates valid shape', () => {
  const def = createDefaultQaDefinition()
  assert.equal(def.question, '')
  assert.equal(def.answer, '')
  assert.equal(def.intent, '')
  assert.equal(def.source, '')
  assert.deepEqual(def.citations, [])
})

test('normalizeQaDefinition handles undefined input', () => {
  const definition = normalizeQaDefinition({})
  assert.equal(definition.question, '')
  assert.equal(definition.answer, '')
  assert.equal(definition.intent, '')
  assert.equal(definition.source, '')
  assert.deepEqual(definition.citations, [])
})
