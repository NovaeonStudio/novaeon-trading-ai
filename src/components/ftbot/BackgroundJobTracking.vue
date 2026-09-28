<script setup lang="ts">
const botStore = useBotStore();
const runningJobs = computed(() => botStore.activeBot.backgroundJobs);

const jobCategoryIcons: Record<string, string> = {
  pairlist: 'mdi-format-list-bulleted',
  download_data: 'mdi-download-box-outline',
  // backtest: 'mdi-chart-timeline-variant-shimmer',
  lookahead_analysis: 'mdi-chart-timeline-variant-shimmer',
  recursive_analysis: 'mdi-magnify-scan',
};
</script>

<template>
  <div v-if="Object.keys(runningJobs).length > 0" class="flex flex-row items-end gap-2">
    <ul class="flex w-full grow flex-col gap-2" :aria-label="$t('jobs.list')">
      <li
        v-for="(job, key) in runningJobs"
        :key="key"
        class="nova-tile flex items-center gap-3 p-3 text-sm"
        :title="job.job_category + ' - ' + job.status"
      >
        <UIcon
          :name="jobCategoryIcons[job.job_category]"
          v-if="job.job_category in jobCategoryIcons"
          :title="job.job_id"
        />
        <span v-else>{{ job.job_category }}</span>
        <div class="flex justify-between">
          <i-mdi-check v-if="job.status === 'success'" class="text-success" title="" />
          <div class="flex gap-2 items-center w-full" v-else-if="job.status === 'failed'">
            <i-mdi-close class="text-error" title="" />
            <span class="text-error">{{ $t('jobs.failed') }}</span>
            <span class="ms-2">{{ job.error }}</span>
          </div>
          <span v-else>{{ job.status }} </span>
          <span v-if="job.progress" class="nova-num w-24">{{ job.progress }}</span>
        </div>
        <UProgress
          v-if="job.progress"
          class="w-full grow"
          color="success"
          :model-value="(job.progress / 100) * 100"
          :max="100"
        />
        <div
          v-if="job.progress_tasks && Object.keys(job.progress_tasks).length > 0"
          class="flex flex-col md:flex-row w-full grow gap-2"
        >
          <div v-for="[tkey, t] in Object.entries(job.progress_tasks)" :key="tkey" class="w-full">
            {{ t.description }}

            <UProgress
              class="w-full grow"
              :model-value="Math.round((t.progress / t.total) * 100 * 100) / 100"
              color="success"
              show-progress
              :pt="{
                value: {
                  class: job.status === 'success' ? 'bg-emerald-500' : 'bg-amber-500',
                },
              }"
              striped
            />
          </div>
        </div>
      </li>
    </ul>
    <UTooltip :text="$t('jobs.clear')">
      <UButton
        color="neutral"
        variant="ghost"
        class="ms-auto"
        icon="i-mdi-broom"
        :aria-label="$t('jobs.clear')"
        @click="botStore.activeBot.clearBgJobs()"
      />
    </UTooltip>
  </div>
</template>
