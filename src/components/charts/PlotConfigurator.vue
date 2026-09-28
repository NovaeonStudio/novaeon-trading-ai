<script setup lang="ts">
import type { IndicatorConfig, PlotConfig } from '@/types';

const props = withDefaults(
  defineProps<{
    columns: string[];
    isVisible?: boolean;
  }>(),
  {
    isVisible: false,
  },
);

const { t } = useI18n();
const plotStore = usePlotConfigStore();
const botStore = useBotStore();

const plotConfigNameLoc = ref('default');
const selIndicatorName = ref('');
const addNewIndicator = ref(false);
const showConfig = ref(false);
const selSubPlot = ref('main_plot');
const tempPlotConfig = ref<PlotConfig>();
const tempPlotConfigValid = ref(true);

const isMainPlot = computed(() => {
  return selSubPlot.value === 'main_plot';
});

const currentPlotConfig = computed(() => {
  if (isMainPlot.value) {
    return plotStore.editablePlotConfig.main_plot;
  }

  return plotStore.editablePlotConfig.subplots[selSubPlot.value];
});
const subplots = computed((): string[] => {
  // Subplot keys (for selection window)
  return ['main_plot', ...Object.keys(plotStore.editablePlotConfig.subplots)];
});
const usedColumns = computed((): { label: string; value: string }[] => {
  let usedCols: string[] = [];
  if (isMainPlot.value) {
    usedCols = Object.keys(plotStore.editablePlotConfig.main_plot);
  }
  const selSubPlot_ = plotStore.editablePlotConfig.subplots[selSubPlot.value];
  if (selSubPlot_) {
    usedCols = Object.keys(selSubPlot_);
  }
  return usedCols.map((col) => ({
    value: col,
    label: !props.columns.includes(col) ? t('plot.configurator.notAvailable', { col }) : col,
  }));
});

function addIndicator(newIndicator: Record<string, IndicatorConfig>) {
  // console.log('Adding indicator', newIndicator);
  const name = Object.keys(newIndicator)[0];
  if (!name) return;

  const indicator = newIndicator[name];
  if (isMainPlot.value) {
    // console.log(`Adding ${name} to MainPlot`);
    plotStore.editablePlotConfig.main_plot[name] = { ...indicator };
  } else {
    // console.log(`Adding ${name} to ${selSubPlot.value}`);
    plotStore.editablePlotConfig.subplots[selSubPlot.value]![name] = { ...indicator };
  }

  plotStore.editablePlotConfig = { ...plotStore.editablePlotConfig };
  // Reset random color
  addNewIndicator.value = false;
}

const selIndicator = computed<Record<string, IndicatorConfig>>({
  get() {
    if (addNewIndicator.value) {
      return {};
    }
    if (selIndicatorName.value) {
      const currentIndicator = currentPlotConfig.value?.[selIndicatorName.value];
      if (currentIndicator) {
        return {
          [selIndicatorName.value]: currentIndicator,
        };
      }
    }
    return {};
  },
  set(newValue: Record<string, IndicatorConfig>) {
    const name = Object.keys(newValue)[0];
    // this.currentPlotConfig[this.selIndicatorName] = { ...newValue[name] };
    // this.emitPlotConfig();
    if (name && newValue) {
      addIndicator(newValue);
    } else {
      addNewIndicator.value = false;
    }
  },
});

const plotConfigJson = computed({
  get() {
    return JSON.stringify(plotStore.editablePlotConfig, null, 2);
  },
  set(newValue: string) {
    try {
      tempPlotConfig.value = JSON.parse(newValue);
      // TODO: Should Validate schema validity (should be PlotConfig type...)
      tempPlotConfigValid.value = true;
    } catch (err) {
      tempPlotConfigValid.value = false;
    }
  },
});

function removeIndicator() {
  if (isMainPlot.value) {
    console.log(`Removing ${selIndicatorName.value} from MainPlot`);
    delete plotStore.editablePlotConfig.main_plot[selIndicatorName.value];
  } else {
    console.log(`Removing ${selIndicatorName.value} from ${selSubPlot.value}`);
    delete plotStore.editablePlotConfig.subplots[selSubPlot.value]?.[selIndicatorName.value];
  }

  plotStore.editablePlotConfig = { ...plotStore.editablePlotConfig };
  selIndicatorName.value = '';
}

function clickAddNewIndicator() {
  addNewIndicator.value = !addNewIndicator.value;
  selIndicatorName.value = '';
}

function addSubplot(newSubplotName: string) {
  plotStore.editablePlotConfig.subplots = {
    ...plotStore.editablePlotConfig.subplots,
    [newSubplotName]: {},
  };
  selSubPlot.value = newSubplotName;
}

function deleteSubplot(subplotName: string) {
  delete plotStore.editablePlotConfig.subplots[subplotName];
  // Reassign to trigger reactivity
  plotStore.editablePlotConfig = { ...plotStore.editablePlotConfig };
  selSubPlot.value = subplots.value[subplots.value.length - 1] ?? 'main_plot';
}

function renameSubplot(oldName: string, newName: string) {
  const oldSubPlot = plotStore.editablePlotConfig.subplots[oldName];
  if (oldSubPlot) {
    plotStore.editablePlotConfig.subplots[newName] = oldSubPlot;
  }
  selSubPlot.value = newName;
  delete plotStore.editablePlotConfig.subplots[oldName];
}

function loadPlotConfig() {
  // Reset from store
  const existingConf = plotStore.customPlotConfigs[plotStore.plotConfigName];
  if (existingConf) {
    plotStore.editablePlotConfig = deepClone(existingConf);
  }
}

function loadConfigFromString() {
  if (tempPlotConfig.value !== undefined && tempPlotConfigValid.value) {
    plotStore.editablePlotConfig = tempPlotConfig.value;
  }
}

// function clearConfig() {
//   // Use empty config
//   plotStore.editablePlotConfig = { ...EMPTY_PLOTCONFIG };
// }

async function loadPlotConfigFromStrategy() {
  if (botStore.activeBot.isWebserverMode && !botStore.activeBot.strategy?.strategy) {
    showAlert(t('plot.configurator.noStrategy'));
    return;
  }
  try {
    const strategyPlotConfig = await botStore.activeBot.getStrategyPlotConfig();
    if (strategyPlotConfig) {
      plotStore.editablePlotConfig = strategyPlotConfig;
    }
  } catch (error) {
    //
    showAlert(t('plot.configurator.loadFailed'));
  }
}

function savePlotConfig() {
  plotStore.saveCustomPlotConfig(plotConfigNameLoc.value, plotStore.editablePlotConfig);
}

function addNewIndicatorSelected(indicator?: string) {
  addNewIndicator.value = false;

  if (indicator) {
    addIndicator({
      [indicator]: {
        color: randomColor(),
      },
    });
    selIndicatorName.value = indicator;
  }
}

watch(selSubPlot, () => {
  // Deselect Indicator when switching selected plot
  selIndicatorName.value = '';
});

watch(
  () => plotStore.plotConfigName,
  () => {
    selIndicatorName.value = '';
    // selSubPlot.value = '';
    plotConfigNameLoc.value = plotStore.plotConfigName;
  },
);

watch(
  () => props.isVisible,
  () => {
    if (props.isVisible) {
      // Deep clone and assign to editable
      plotStore.editablePlotConfig = deepClone(plotStore.plotConfig);
      plotStore.isEditing = true;
      plotConfigNameLoc.value = plotStore.plotConfigName;
    } else {
      plotStore.isEditing = false;
    }
  },
  {
    immediate: true,
  },
);
const fromPlotTemplateVisible = ref(false);

const showTagsInTooltips = computed({
  get() {
    return plotStore.editablePlotConfig.options?.showTags ?? true;
  },
  set(value: boolean) {
    if (!plotStore.editablePlotConfig.options) {
      plotStore.editablePlotConfig.options = {};
    }
    plotStore.editablePlotConfig.options.showTags = value;
  },
});
const markAreaZIndex = computed({
  get() {
    return plotStore.editablePlotConfig.options?.markAreaZIndex ?? 1;
  },
  set(value: number) {
    if (!plotStore.editablePlotConfig.options) {
      plotStore.editablePlotConfig.options = {};
    }
    plotStore.editablePlotConfig.options.markAreaZIndex = value;
  },
});
</script>

<template>
  <div v-if="columns">
    <UFormField :label="t('plot.configurator.configName')" class="text-md">
      <PlotConfigSelect allow-edit></PlotConfigSelect>
    </UFormField>
    <USeparator class="my-2" />
    <BaseCheckbox v-model="showTagsInTooltips" class="mb-1">{{
      t('plot.configurator.showTags')
    }}</BaseCheckbox>
    <div class="grid grid-cols-2 items-center gap-2 w-full">
      <label
        >{{ t('plot.configurator.markAreaZ') }} <br /><small>{{
          t('plot.configurator.markAreaZHint')
        }}</small></label
      >

      <UInputNumber v-model="markAreaZIndex" class="mb-1" />
    </div>
    <USeparator class="my-2" />

    <UFormField :label="t('plot.configurator.targetPlot')" class="text-md">
      <EditValue
        v-model="selSubPlot"
        :allow-edit="!isMainPlot"
        allow-add
        :editable-name="t('plot.editableName')"
        align-vertical
        @new="addSubplot"
        @delete="deleteSubplot"
        @rename="renameSubplot"
      >
        <UListbox
          id="fieldSel"
          v-model="selSubPlot"
          value-key="value"
          :items="
            subplots.map((plot) => ({
              value: plot,
              label: plot,
            }))
          "
        >
        </UListbox>
      </EditValue>
    </UFormField>
    <USeparator class="my-2" />
    <UFormField :label="t('plot.configurator.indicators')" class="text-md">
      <UListbox v-model="selIndicatorName" value-key="value" :items="usedColumns"> </UListbox>
    </UFormField>
    <div class="flex flex-row flex-wrap mt-1 gap-1">
      <UButton
        color="neutral"
        :title="t('plot.configurator.removeTitle')"
        :disabled="!selIndicatorName"
        class="col"
        @click="removeIndicator"
        :label="t('plot.configurator.remove')"
        icon="mdi:minus-box-outline"
      />

      <UButton
        color="neutral"
        :title="t('plot.configurator.fromTemplateTitle')"
        @click="fromPlotTemplateVisible = !fromPlotTemplateVisible"
        :label="t('plot.configurator.fromTemplate')"
        icon="mdi:folder-arrow-down-outline"
      />

      <UButton
        :title="t('plot.configurator.addTitle')"
        icon="mdi:plus-box-outline"
        class="col"
        :disabled="addNewIndicator"
        @click="clickAddNewIndicator"
        :label="t('plot.configurator.add')"
      />
    </div>

    <PlotIndicatorSelect
      v-if="addNewIndicator"
      :columns="columns"
      class="mt-1"
      :label="t('plot.configurator.selectToAdd')"
      @indicator-selected="addNewIndicatorSelected"
    />

    <PlotFromTemplate v-model:visible="fromPlotTemplateVisible" :columns="columns" />

    <PlotIndicator
      v-if="selIndicatorName && !fromPlotTemplateVisible"
      v-model="selIndicator"
      class="mt-1"
      :columns="columns"
    />
    <USeparator class="my-2" />

    <div class="flex flex-row flex-wrap gap-1">
      <UButton
        color="neutral"
        :disabled="addNewIndicator"
        :title="t('plot.configurator.resetTitle')"
        @click="loadPlotConfig"
        :label="t('common.reset')"
        icon="mdi:restore"
      />

      <!--
        Does Resetting a config to "nothing" make sense, or can this be done via "delete / create"?
        <UButton
        class="ms-1 "
        color="neutral"
        :disabled="addNewIndicator"
        title="Start with empty configuration"
        @click="clearConfig"
        >Reset</UButton
      > -->
      <UButton
        :disabled="
          (botStore.activeBot.isWebserverMode &&
            !botStore.activeBot.botFeatures.plotConfigFromServer) ||
          !botStore.activeBot.isBotOnline ||
          addNewIndicator
        "
        color="neutral"
        :label="t('plot.configurator.fromStrategy')"
        icon="mdi:download"
        @click="loadPlotConfigFromStrategy"
      />

      <UButton
        id="showButton"
        color="neutral"
        :disabled="addNewIndicator"
        :title="t('plot.configurator.showConfigTitle')"
        @click="showConfig = !showConfig"
        :icon="showConfig ? 'mdi:eye-off' : 'mdi:eye'"
        :label="showConfig ? t('common.hide') : t('common.show')"
      />

      <UButton
        data-toggle="tooltip"
        :disabled="addNewIndicator"
        :title="t('plot.configurator.saveTitle')"
        @click="savePlotConfig"
        :label="t('common.save')"
        variant="solid"
        icon="mdi:content-save"
      />
    </div>
    <UButton
      v-if="showConfig"
      class="mt-1"
      color="neutral"
      size="sm"
      :title="t('plot.configurator.loadStringTitle')"
      @click="loadConfigFromString"
      icon="mdi:upload"
      >{{ t('plot.configurator.loadString') }}</UButton
    >
    <div v-if="showConfig" class="w-full ms-1 mt-2">
      <UTextarea
        id="TextArea"
        v-model="plotConfigJson"
        class="w-full"
        autoresize
        :maxrows="10"
        :state="tempPlotConfigValid"
      >
      </UTextarea>
    </div>
  </div>
</template>
