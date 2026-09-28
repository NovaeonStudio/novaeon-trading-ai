<script setup lang="ts">
import type { LookaheadAnalysisPayload, LookaheadResult } from '@/types';

const { t } = useI18n();
const botStore = useBotStore();

const running = ref(false);
const result = ref<LookaheadResult | null>(null);
const statusMessage = ref('');

async function startAnalysis(payload: LookaheadAnalysisPayload) {
  running.value = true;
  result.value = null;
  statusMessage.value = '';
  try {
    const { job_id: jobId } = await botStore.activeBot.startLookaheadAnalysis(payload);
    const status = await botStore.activeBot.pollBgJob(jobId, 'lookahead_analysis');
    if (status.status === 'failed') {
      statusMessage.value = status.error || t('analysis.lookahead.failed');
      showAlert(statusMessage.value, 'error');
      return;
    }
    const analysis = await botStore.activeBot.getLookaheadAnalysisResult(jobId);
    if (analysis.status === 'ended') {
      result.value = analysis.result;
      statusMessage.value = analysis.status_msg;
    } else {
      statusMessage.value = analysis.status_msg || t('analysis.lookahead.failed');
      showAlert(statusMessage.value, 'error');
    }
  } catch (error) {
    console.error(error);
    showAlert(t('analysis.lookahead.runError'), 'error');
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <div class="flex w-full min-w-0 flex-col gap-6 text-start">
    <BackgroundJobTracking />
    <NovaPanel :title="t('analysis.settings')">
      <LookaheadAnalysisForm :running="running" @start="startAnalysis" />
    </NovaPanel>
    <NovaPanel v-if="result" :title="t('analysis.result')">
      <LookaheadAnalysisResults :result="result" />
    </NovaPanel>
  </div>
</template>
