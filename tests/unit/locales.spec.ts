import { describe, expect, it } from 'vitest';
import de from '@/locales/de.json';
import en from '@/locales/en.json';
import ro from '@/locales/ro.json';

type Tree = { [key: string]: string | Tree };

function flatten(tree: Tree, prefix = '', out: Record<string, unknown> = {}) {
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object') flatten(value, path, out);
    else out[path] = value;
  }
  return out;
}

const locales = { en, de, ro } as Record<string, Tree>;
const flat = Object.fromEntries(Object.entries(locales).map(([l, tree]) => [l, flatten(tree)]));
const enKeys = Object.keys(flat.en!).sort();

describe('locale files', () => {
  it('have translations at all', () => {
    expect(enKeys.length).toBeGreaterThan(100);
  });

  it.each(['de', 'ro'])('%s has exactly the English key set', (lang) => {
    expect(Object.keys(flat[lang]!).sort()).toEqual(enKeys);
  });

  it.each(['en', 'de', 'ro'])('%s has no empty or non-text values', (lang) => {
    const bad = Object.entries(flat[lang]!).filter(
      ([, value]) => typeof value !== 'string' || value.trim() === '',
    );
    expect(bad).toEqual([]);
  });
});
