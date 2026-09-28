<script setup lang="ts">
/** ⌘K / Ctrl+K command palette: navigate, act on the bot (with confirmation), jump to any pair's chart. */
import type { CommandPaletteGroup, CommandPaletteItem } from '@nuxt/ui';

const { t: tr } = useI18n();
const { paletteOpen: open } = useNovaPalette();
const router = useRouter();
const botStore = useBotStore();
const colorMode = useColorMode();
const { privacy, togglePrivacy } = useNovaPrivacy();
const { confirm } = useConfirmBox();
const nav = useNovaNav();

defineShortcuts({
  meta_k: () => {
    open.value = !open.value;
  },
  shift_p: () => togglePrivacy(),
});

function go(to: string) {
  router.push(to);
}

async function guarded(title: string, message: string, action: () => Promise<unknown>) {
  if (await confirm({ title, message })) await action();
}

const groups = computed<CommandPaletteGroup<CommandPaletteItem>[]>(() => {
  const bot = botStore.hasBots ? botStore.activeBot : null;
  const pages: CommandPaletteItem[] = nav.flat.value.map((item) => ({
    label: item.label,
    icon: item.icon,
    suffix: item.hint,
    onSelect: () => go(item.to),
  }));
  const view: CommandPaletteItem[] = [
    {
      label: privacy.value ? tr('palette.showBalances') : tr('palette.hideBalances'),
      icon: privacy.value ? 'i-mdi-eye' : 'i-mdi-eye-off',
      kbds: ['shift', 'P'],
      onSelect: togglePrivacy,
    },
    {
      label: colorMode.value === 'dark' ? tr('palette.lightMode') : tr('palette.darkMode'),
      icon: 'i-mdi-theme-light-dark',
      onSelect: () => {
        colorMode.value = colorMode.value === 'dark' ? 'light' : 'dark';
      },
    },
  ];
  const out: CommandPaletteGroup<CommandPaletteItem>[] = [
    { id: 'pages', label: tr('palette.group.goTo'), items: pages },
    { id: 'view', label: tr('palette.group.view'), items: view },
  ];
  if (bot?.isBotOnline) {
    out.push({
      id: 'bot',
      label: tr('palette.group.bot', { name: bot.uiBotName }),
      items: [
        {
          label: tr('palette.pause.label'),
          suffix: tr('palette.pause.suffix'),
          icon: 'i-mdi-pause-circle',
          onSelect: () =>
            guarded(tr('palette.pause.title'), tr('palette.pause.message'), () => bot.stopBuy()),
        },
        {
          label: tr('palette.start.label'),
          icon: 'i-mdi-play-circle',
          onSelect: () =>
            guarded(tr('palette.start.title'), tr('palette.start.message'), () => bot.startBot()),
        },
        {
          label: tr('palette.stop.label'),
          icon: 'i-mdi-stop-circle',
          onSelect: () =>
            guarded(tr('palette.stop.title'), tr('palette.stop.message'), () => bot.stopBot()),
        },
        {
          label: tr('palette.reload.label'),
          icon: 'i-mdi-reload',
          onSelect: () =>
            guarded(tr('palette.reload.title'), tr('palette.reload.message'), () =>
              bot.reloadConfig(),
            ),
        },
      ],
    });
    out.push({
      id: 'pairs',
      label: tr('palette.group.pairs'),
      items: (bot.whitelist ?? []).map((pair) => ({
        label: pair,
        icon: 'i-mdi-finance',
        suffix: bot.openTrades.some((t) => t.pair === pair)
          ? tr('palette.openPosition')
          : undefined,
        onSelect: () => {
          bot.selectedPair = pair;
          go('/markets');
        },
      })),
    });
  }
  return out;
});
</script>

<template>
  <UModal v-model:open="open" :ui="{ content: 'max-w-xl rounded-2xl' }">
    <template #content>
      <UCommandPalette
        :groups="groups"
        :placeholder="tr('palette.placeholder')"
        class="h-96"
        :ui="{
          label: 'text-xs font-medium text-muted',
          item: 'rounded-lg transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]',
          itemTrailingKbds: 'opacity-70',
          empty: 'text-sm text-muted',
        }"
        close
        @update:open="open = $event"
        @update:model-value="open = false"
      />
    </template>
  </UModal>
</template>
