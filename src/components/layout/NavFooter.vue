<script setup lang="ts">
const { t } = useI18n();
const botStore = useBotStore();
const route = useRoute();
const { tabs } = useNovaNav();
/** Simple mode on phones: a bottom tab bar with the (at most 4) main destinations. */
const showTabs = computed(
  () => tabs.value.length > 0 && botStore.hasBots && route.path !== '/login',
);
/**
 * Pro mode on phones (trade mode bots): quick links. These used to point at the classic pages
 * (which now forward to their successors), so they link to the successors directly.
 */
const proLinks = computed(() => [
  { label: t('nav.item.command'), to: '/command', icon: 'i-mdi-radar' },
  { label: t('nav.item.positions'), to: '/positions', icon: 'i-mdi-briefcase-outline' },
  { label: t('nav.item.trades'), to: '/trades', icon: 'i-mdi-history' },
  { label: t('nav.item.pairlist'), to: '/pairlist', icon: 'i-mdi-format-list-group' },
]);
const items = computed(() => (showTabs.value ? tabs.value : proLinks.value));
const show = computed(
  () => showTabs.value || (!botStore.canRunBacktest && botStore.hasBots && route.path !== '/login'),
);
function isActive(to: string) {
  return route.path === to || route.path.startsWith(`${to}/`);
}
</script>

<template>
  <nav
    v-if="show"
    :aria-label="t('nav.main')"
    class="nova-tabbar border-t border-default/70 pb-[env(safe-area-inset-bottom)] md:hidden"
  >
    <div class="mx-auto grid max-w-lg grid-cols-4">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        :aria-current="isActive(item.to) ? 'page' : undefined"
        class="group flex min-h-16 flex-col items-center justify-center gap-1 text-xs font-medium transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-400/60 active:scale-[0.98]"
        :class="isActive(item.to) ? 'text-highlighted' : 'text-muted hover:text-default'"
      >
        <span
          class="flex h-8 w-16 items-center justify-center rounded-full transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
          :class="isActive(item.to) ? 'bg-brand-400/15' : 'group-hover:bg-elevated'"
        >
          <UIcon
            :name="item.icon"
            class="size-6"
            :class="isActive(item.to) ? 'text-brand-400' : ''"
          />
        </span>
        <span class="max-w-full px-1 text-center leading-tight text-balance">{{ item.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>
