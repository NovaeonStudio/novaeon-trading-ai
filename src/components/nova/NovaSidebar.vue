<script setup lang="ts">
/** Left app rail: sectioned navigation, collapsible to icons, remembered per browser. */
const { t } = useI18n();
const { sections } = useNovaNav();
const route = useRoute();
const collapsed = useStorage('nova-sidebar-collapsed', false);
const engineOpen = useStorage('nova-sidebar-engine-open', false);
const settingsStore = useSettingsStore();
const { mode } = useNovaMode();

function isActive(to: string) {
  return route.path === to || route.path.startsWith(`${to}/`);
}
</script>

<template>
  <aside
    class="nova-sidebar flex shrink-0 flex-col border-e border-default/70 py-3 transition-[width] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
    :aria-label="t('nav.sidebar')"
    :class="collapsed ? 'w-16' : 'w-56'"
  >
    <nav class="flex-1 overflow-y-auto px-2" :aria-label="t('nav.main')">
      <div
        v-for="section in sections"
        :key="section.id"
        class="mb-4"
        :class="{ 'mt-6': section.secondary && !collapsed }"
      >
        <button
          v-if="section.collapsible"
          type="button"
          class="nova-label mb-1 flex min-h-8 w-full items-center justify-between rounded-lg px-2 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:text-default focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
          :title="section.label"
          :aria-expanded="engineOpen"
          @click="engineOpen = !engineOpen"
        >
          <span v-if="!collapsed">{{ section.label }}</span>
          <UIcon :name="engineOpen ? 'i-mdi-chevron-up' : 'i-mdi-chevron-down'" class="size-4" />
        </button>
        <div v-else-if="!collapsed" class="nova-label mb-1 px-2 text-start">
          {{ section.label }}
        </div>
        <div v-else class="mx-3 mb-2 h-px bg-default/70" />
        <template v-if="!section.collapsible || engineOpen">
          <RouterLink
            v-for="item in section.items"
            :key="item.to"
            :to="item.to"
            class="group relative mb-0.5 flex items-center gap-3 rounded-lg px-3 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
            :class="[
              isActive(item.to)
                ? 'bg-brand-400/10 text-highlighted'
                : 'text-muted hover:bg-accented/60 hover:text-default',
              section.secondary ? 'py-1.5 text-sm' : 'py-2 text-sm',
            ]"
            :title="collapsed ? item.label : item.hint"
            :aria-current="isActive(item.to) ? 'page' : undefined"
          >
            <span
              v-if="isActive(item.to)"
              class="absolute inset-y-2 start-0 w-0.5 rounded-full bg-brand-400"
            />
            <UIcon
              :name="item.icon"
              class="shrink-0"
              :class="[
                isActive(item.to) ? 'text-brand-400' : 'text-dimmed group-hover:text-muted',
                section.secondary ? 'size-4' : 'size-5',
              ]"
            />
            <span v-if="!collapsed" class="truncate">{{ item.label }}</span>
          </RouterLink>
        </template>
      </div>
    </nav>
    <div v-if="!collapsed" class="mx-2 mb-2">
      <div class="nova-label mb-1 px-2 text-start">{{ t('nav.view') }}</div>
      <div
        class="nova-seg grid! w-full grid-cols-2 text-sm"
        role="group"
        :aria-label="t('nav.viewMode')"
      >
        <button
          v-for="m in ['simple', 'pro'] as const"
          :key="m"
          type="button"
          class="min-h-8 font-medium"
          :aria-pressed="mode === m"
          :title="m === 'simple' ? t('nav.simpleHint') : t('nav.proHint')"
          @click="mode = m"
        >
          {{ m === 'simple' ? t('common.simple') : t('common.pro') }}
        </button>
      </div>
    </div>
    <div
      class="flex items-center gap-1 border-t border-default/70 px-2 pt-2"
      :class="collapsed ? 'flex-col' : ''"
    >
      <ThemeSelect />
      <span
        v-if="!collapsed"
        class="flex-1 truncate text-xs text-dimmed"
        :title="
          t('nav.versionTitle', {
            version: settingsStore.uiVersion.replace(/^not_installed-/, ''),
          })
        "
        >{{ settingsStore.uiVersion.replace(/^not_installed-/, '') }}</span
      >
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        :icon="collapsed ? 'i-mdi-chevron-double-right' : 'i-mdi-chevron-double-left'"
        :aria-label="collapsed ? t('nav.expand') : t('nav.collapse')"
        @click="collapsed = !collapsed"
      />
    </div>
  </aside>
</template>
