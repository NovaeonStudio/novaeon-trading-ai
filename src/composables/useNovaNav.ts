import { t } from '@/i18n';

/** Single source of truth for NovaeonTradingAI navigation (sidebar, mobile menu, ⌘K palette). */
export interface NovaNavItem {
  label: string;
  to: string;
  icon: string;
  hint?: string;
}
export interface NovaNavSection {
  id: string;
  label: string;
  items: NovaNavItem[];
  collapsible?: boolean;
  /** Rendered smaller and quieter (Simple mode "More" group). */
  secondary?: boolean;
}

/**
 * Simple mode's main destinations (sidebar top group and the mobile bottom tab bar). At most 4.
 * Computed so the labels follow a language switch.
 */
export const SIMPLE_MAIN = computed<NovaNavItem[]>(() => [
  { label: t('nav.item.home'), to: '/home', icon: 'i-mdi-home-outline', hint: t('nav.hint.home') },
  {
    label: t('nav.item.myCoins'),
    to: '/positions',
    icon: 'i-mdi-hand-coin-outline',
    hint: t('nav.hint.myCoins'),
  },
  {
    label: t('nav.item.history'),
    to: '/trades',
    icon: 'i-mdi-history',
    hint: t('nav.hint.history'),
  },
  {
    label: t('nav.item.wallet'),
    to: '/wallet',
    icon: 'i-mdi-wallet-outline',
    hint: t('nav.hint.wallet'),
  },
]);

export function useNovaNav() {
  const botStore = useBotStore();

  const { simple } = useNovaMode();

  const sections = computed<NovaNavSection[]>(() => {
    const bot = botStore.hasBots ? botStore.activeBot : null;
    const webserver = bot?.isWebserverMode ?? false;
    if (simple.value && !webserver) {
      return [
        {
          id: 'simple',
          label: t('nav.section.myBot'),
          items: SIMPLE_MAIN.value,
        },
        {
          id: 'more',
          label: t('nav.section.more'),
          secondary: true,
          items: [
            {
              label: t('nav.item.strategy'),
              to: '/lab',
              icon: 'i-mdi-flask-outline',
              hint: t('nav.hint.strategy'),
            },
            {
              label: t('nav.item.bots'),
              to: '/',
              icon: 'i-mdi-robot-outline',
              hint: t('nav.hint.bots'),
            },
            { label: t('nav.item.settings'), to: '/settings', icon: 'i-mdi-cog-outline' },
          ],
        },
      ];
    }
    const out: NovaNavSection[] = [];
    if (!webserver) {
      out.push(
        {
          id: 'overview',
          label: t('nav.section.overview'),
          items: [
            {
              label: t('nav.item.home'),
              to: '/home',
              icon: 'i-mdi-home-outline',
              hint: t('nav.hint.homePro'),
            },
            {
              label: t('nav.item.command'),
              to: '/command',
              icon: 'i-mdi-radar',
              hint: t('nav.hint.command'),
            },
            {
              label: t('nav.item.cockpit'),
              to: '/cockpit',
              icon: 'i-mdi-gauge',
              hint: t('nav.hint.cockpit'),
            },
          ],
        },
        {
          id: 'trading',
          label: t('nav.section.trading'),
          items: [
            {
              label: t('nav.item.positions'),
              to: '/positions',
              icon: 'i-mdi-briefcase-outline',
              hint: t('nav.hint.positions'),
            },
            {
              label: t('nav.item.markets'),
              to: '/markets',
              icon: 'i-mdi-finance',
              hint: t('nav.hint.markets'),
            },
            {
              label: t('nav.item.trades'),
              to: '/trades',
              icon: 'i-mdi-history',
              hint: t('nav.hint.trades'),
            },
            {
              label: t('nav.item.strategyLab'),
              to: '/lab',
              icon: 'i-mdi-flask-outline',
              hint: t('nav.hint.strategyLab'),
            },
          ],
        },
      );
    }
    out.push({
      id: 'system',
      label: t('nav.section.system'),
      items: [
        {
          label: t('nav.item.wallet'),
          to: '/wallet',
          icon: 'i-mdi-wallet-outline',
          hint: t('nav.hint.walletPro'),
        },
        {
          label: t('nav.item.journal'),
          to: '/journal',
          icon: 'i-mdi-text-box-search-outline',
          hint: t('nav.hint.journal'),
        },
        {
          label: t('nav.item.bots'),
          to: '/',
          icon: 'i-mdi-robot-outline',
          hint: t('nav.hint.bots'),
        },
        { label: t('nav.item.settings'), to: '/settings', icon: 'i-mdi-cog-outline' },
      ],
    });
    const tools: NovaNavItem[] = [
      { label: t('nav.item.backtest'), to: '/backtest', icon: 'i-mdi-flask-outline' },
    ];
    if (webserver && bot?.botFeatures.downloadDataView)
      tools.push({
        label: t('nav.item.downloadData'),
        to: '/download_data',
        icon: 'i-mdi-download',
      });
    if (webserver && bot?.botFeatures.pairlistConfig)
      tools.push({
        label: t('nav.item.pairlistConfig'),
        to: '/pairlist_config',
        icon: 'i-mdi-format-list-numbered-rtl',
      });
    if (webserver && bot?.botFeatures.recursiveAnalysis)
      tools.push({
        label: t('nav.item.recursiveAnalysis'),
        to: '/recursive_analysis',
        icon: 'i-mdi-magnify-scan',
      });
    if (webserver && bot?.botFeatures.lookaheadAnalysis)
      tools.push({
        label: t('nav.item.lookaheadAnalysis'),
        to: '/lookahead_analysis',
        icon: 'i-mdi-chart-timeline-variant-shimmer',
      });
    out.push({ id: 'engine', label: t('nav.section.engine'), items: tools, collapsible: true });
    return out;
  });

  const flat = computed(() => sections.value.flatMap((s) => s.items));
  /** Mobile bottom tab bar (Simple mode only; empty in Pro and webserver mode). */
  const tabs = computed<NovaNavItem[]>(() =>
    simple.value && !(botStore.hasBots && botStore.activeBot?.isWebserverMode)
      ? SIMPLE_MAIN.value
      : [],
  );
  return { sections, flat, tabs };
}
