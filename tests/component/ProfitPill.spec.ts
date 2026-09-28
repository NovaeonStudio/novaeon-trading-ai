import ProfitPill from '@/components/general/ProfitPill.vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

describe('ProfitPill.vue', () => {
  it('Shows a Green pill with positive profits', () => {
    const wrapper = mount(ProfitPill, {
      props: {
        profitRatio: 0.051,
        profitAbs: 0.1,
        profitDesc: '',
        stakeCurrency: 'USDT',
      },
    });
    expect(wrapper.find('div').classes()).toContain('text-emerald-400');
    expect(wrapper.find('div').text()).toContain('5.10%');
    expect(wrapper.find('div').text()).toContain('(0.1)');
    expect(wrapper.find('span[title]').element.title).toBe('USDT');
  });
  it('Shows a Red pill with positive profits', () => {
    const wrapper = mount(ProfitPill, {
      props: {
        profitRatio: -0.1,
        profitAbs: -0.1,
        profitDesc: '',
        stakeCurrency: 'USDT',
      },
    });

    expect(wrapper.get('div').classes()).not.toContain('text-emerald-400');
    expect(wrapper.get('div').classes()).toContain('text-rose-400');
    expect(wrapper.get('div').text()).toContain('-10.00%');
    expect(wrapper.get('div').text()).toContain('(-0.1)');
    expect(wrapper.get('span[title]').element.title).toBe('USDT');
  });
  it('Shows a pill with 0.0 profits.', () => {
    const wrapper = mount(ProfitPill, {
      props: {
        profitRatio: 0.0,
        profitAbs: 0.0,
        profitDesc: '',
        stakeCurrency: 'BTC',
      },
    });

    expect(wrapper.get('div').classes()).toContain('text-rose-400');
    expect(wrapper.get('div').text()).toContain('0.00%');
    expect(wrapper.get('div').text()).toContain('(0)');
    expect(wrapper.get('span[title]').element.title).toBe('BTC');
  });
  it('Shows a pill without relative profits.', () => {
    const wrapper = mount(ProfitPill, {
      props: {
        profitRatio: undefined,
        profitAbs: 223,
        profitDesc: '',
        stakeCurrency: 'USDT',
      },
    });

    expect(wrapper.get('div').classes()).toContain('text-emerald-400');
    expect(wrapper.get('div').text()).not.toContain('%');
    expect(wrapper.get('div').text()).toContain('223');
    expect(wrapper.get('span[title]').element.title).toBe('USDT');
  });
  it('Shows a pill without profits.', () => {
    const wrapper = mount(ProfitPill, {
      props: {
        profitRatio: undefined,
        profitAbs: undefined,
        profitDesc: '',
        stakeCurrency: 'USDT',
      },
    });

    expect(wrapper.get('div').classes()).toContain('text-muted');
    expect(wrapper.get('div').text()).not.toContain('%');
  });
});
