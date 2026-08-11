import { describe, expect, it } from 'vitest'
import { de } from './de'
import { en } from './en'

type Node = { [key: string]: string | Node }

/** Every leaf key, flattened to dotted paths. */
function keysOf(node: Node, prefix = ''): string[] {
  return Object.entries(node).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return typeof value === 'string' ? [path] : keysOf(value, path)
  })
}

/** Placeholders such as {{km}} and markup slots such as <0>. */
function slotsOf(text: string): string[] {
  return [...text.matchAll(/\{\{(\w+)\}\}|<(\d+)>/g)]
    .map((match) => match[1] ?? `<${match[2]}>`)
    .sort()
}

function leaves(node: Node, prefix = ''): [string, string][] {
  return Object.entries(node).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return typeof value === 'string'
      ? ([[path, value]] as [string, string][])
      : leaves(value, path)
  })
}

describe('translations', () => {
  it('cover the same keys in every language', () => {
    expect(keysOf(en as Node).sort()).toEqual(keysOf(de as Node).sort())
  })

  it('has no empty strings', () => {
    for (const [key, value] of [...leaves(de as Node), ...leaves(en as Node)]) {
      expect(value.trim(), key).not.toBe('')
    }
  })

  it('uses the same placeholders in both languages', () => {
    const german = new Map(leaves(de as Node))

    for (const [key, english] of leaves(en as Node)) {
      expect(slotsOf(english), key).toEqual(slotsOf(german.get(key) as string))
    }
  })

  it('keeps error codes in step with the ones the API can send', () => {
    const codes = [
      'empty_upload',
      'too_large',
      'bad_start_time',
      'bad_speed',
      'unreadable_route',
      'empty_route',
      'unknown',
    ]
    expect(Object.keys(de.errors).sort()).toEqual([...codes].sort())
  })
})
