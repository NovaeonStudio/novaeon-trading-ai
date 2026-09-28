<script setup lang="ts">
import { I18nT } from 'vue-i18n';
import { intlLocale } from '@/i18n';
/**
 * Wallet & real money (Simple and Pro): connect MetaMask, let the bot trade via a Hyperliquid API wallet,
 * and switch between practice money and real money. All checks are enforced again by the control service.
 */
import { controlErrorText, useNovaControl } from '@/composables/useNovaControl';

const { t } = useI18n();
const { bot } = useNovaLive();
const {
  status,
  loading,
  error,
  account,
  accountBalance,
  hasMetaMask,
  refresh,
  connect,
  approveBot,
  forgetWallet,
  setMode,
  practiceInfo,
  restarting,
  practice,
  addPractice,
  resetPractice,
  botSettings,
} = useNovaControl();
const { confirm } = useConfirmBox();
const toast = useToast();
const route = useRoute();

const busy = ref<string | null>(null);
const actionError = ref<string | null>(null);
const capital = ref<number>(0);
const typed = ref('');
const ack = ref({ lose: false, noGuarantee: false, leverage: false });
const showGoLive = ref(false);

let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  refresh();
  timer = setInterval(refresh, 30000);
});
onUnmounted(() => clearInterval(timer));

const live = computed(() => status.value?.mode === 'live');
const wallet = computed(() => status.value?.wallet);
/** Balance of the bot's wallet, or of the freshly connected MetaMask account before approval. */
const balanceInfo = computed(() => accountBalance.value ?? wallet.value?.balance ?? null);
const balance = computed(() => balanceInfo.value?.total ?? 0);
const connectedAddr = computed(() => wallet.value?.address ?? account.value);
const walletMismatch = computed(
  () =>
    !!account.value &&
    !!wallet.value?.address &&
    account.value.toLowerCase() !== wallet.value.address.toLowerCase(),
);
const openTrades = computed(() => status.value?.engine.open_trades ?? 0);
const soldCount = computed(() => bot.value?.closedTrades?.length ?? 0);
const minCapital = computed(() => status.value?.minCapital ?? 20);
const phrase = computed(() => status.value?.confirmPhrase ?? 'REAL MONEY');

const step = computed(() => {
  if (!connectedAddr.value) return 1;
  if (balance.value < minCapital.value) return 2;
  if (!wallet.value?.approved || walletMismatch.value) return 3;
  return 4;
});
const canGoLive = computed(
  () =>
    step.value === 4 &&
    capital.value >= minCapital.value &&
    capital.value <= balance.value &&
    ack.value.lose &&
    ack.value.noGuarantee &&
    ack.value.leverage &&
    typed.value.trim().toUpperCase() === phrase.value,
);

function short(a?: string | null) {
  return a ? `${a.slice(0, 6)}…${a.slice(-4)}` : '';
}

async function run(name: string, fn: () => Promise<unknown>) {
  busy.value = name;
  actionError.value = null;
  try {
    await fn();
  } catch (e) {
    actionError.value = controlErrorText(e);
  } finally {
    busy.value = null;
  }
}

const doConnect = () => run('connect', connect);
const doApprove = () => run('approve', approveBot);
async function doForget() {
  if (
    await confirm({
      title: t('wallet.confirm.disconnectTitle'),
      message: t('wallet.confirm.disconnectMessage'),
    })
  )
    await run('forget', forgetWallet);
}
function openGoLive() {
  capital.value = Math.floor(Math.min(balance.value, 100));
  typed.value = '';
  ack.value = { lose: false, noGuarantee: false, leverage: false };
  showGoLive.value = true;
}
async function doGoLive() {
  await run('live', () => setMode('live', capital.value, typed.value));
  if (!actionError.value) showGoLive.value = false;
}
async function doBackToPractice() {
  if (
    await confirm({
      title: t('wallet.confirm.backTitle'),
      message: t('wallet.confirm.backMessage'),
    })
  )
    await run('paper', () => setMode('paper'));
}

/* ---------- Practice money (paper trading only) ---------- */
const QUICK_ADD = [500, 1000, 5000];
/** Space between two translated sentences in the template (Vue drops leading whitespace inside <template>). */
const SPACE = ' ';
const usdc = (v: number) => novaMoney(v, 'USDC', Number.isInteger(v) ? 0 : 2);
const practiceError = ref<string | null>(null);
const practiceLoadError = ref<string | null>(null);
const addAmount = ref<number | null>(1000);
const showReset = ref(false);
const resetAmount = ref<number | null>(1000);
const resetAck = ref(false);

const practiceMax = computed(() => practiceInfo.value?.max ?? 1_000_000);
const practiceNow = computed(() => practiceInfo.value?.dry_run_wallet ?? 0);
/** How much can still be added before the total cap. */
const practiceRoom = computed(() => Math.max(0, practiceMax.value - practiceNow.value));
const practiceStartedOn = computed(() => {
  const ts = practiceInfo.value?.started_at;
  return ts
    ? new Date(ts * 1000).toLocaleDateString(intlLocale(), {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : null;
});
const practiceBusy = computed(
  () => restarting.value || busy.value === 'practice-add' || busy.value === 'practice-reset',
);

/** Same rules as the control service: a number from 1 to the cap, and the total stays under the cap. */
function amountProblem(v: number | null | undefined, room: number): string | null {
  if (v === null || v === undefined || Number.isNaN(v)) return t('practice.problem.enterAmount');
  if (v < 1) return t('practice.problem.atLeastOne');
  const max = usdc(practiceMax.value);
  if (v > practiceMax.value) return t('practice.problem.overLimit', { max });
  if (v > room)
    return room < 1
      ? t('practice.problem.capReached', { max })
      : t('practice.problem.capRoom', { max, room: usdc(Math.floor(room)) });
  return null;
}
const addProblem = computed(() => amountProblem(addAmount.value, practiceRoom.value));
const resetProblem = computed(() => amountProblem(resetAmount.value, practiceMax.value));

async function loadPractice() {
  try {
    await practice();
    practiceLoadError.value = null;
  } catch (e) {
    practiceLoadError.value = controlErrorText(e);
  }
}
watch(
  () => status.value?.mode,
  (mode) => {
    if (mode === 'paper') loadPractice();
  },
  { immediate: true },
);

/** /wallet#practice: the page scrolls inside the app shell, so jump to the card once it exists. */
watch(
  () => !!status.value && !!practiceInfo.value,
  (ready) => {
    if (ready && route.hash === '#practice')
      nextTick(() =>
        document.getElementById('practice')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
      );
  },
  { immediate: true },
);

function practiceDone(title: string, engineBack: boolean) {
  toast.add(
    engineBack
      ? { title, color: 'success', icon: 'i-mdi-check-circle-outline' }
      : {
          title,
          description: t('practice.slowBack'),
          color: 'warning',
          icon: 'i-mdi-timer-sand',
        },
  );
}

async function doAddPractice() {
  const amount = addAmount.value;
  if (amount === null || addProblem.value) return;
  const ok = await confirm({
    title: t('practice.addConfirmTitle', { amount: usdc(amount) }),
    message: t('practice.addConfirmMessage', {
      from: usdc(practiceNow.value),
      to: usdc(practiceNow.value + amount),
    }),
    confirmText: t('practice.addButton'),
  });
  if (!ok) return;
  busy.value = 'practice-add';
  practiceError.value = null;
  try {
    const res = await addPractice(amount);
    practiceDone(t('practice.addedToast', { amount: usdc(res.dry_run_wallet) }), res.engineBack);
  } catch (e) {
    practiceError.value = controlErrorText(e);
  } finally {
    busy.value = null;
  }
}

function openReset() {
  resetAmount.value = 1000;
  resetAck.value = false;
  practiceError.value = null;
  showReset.value = true;
}
async function doResetPractice() {
  const amount = resetAmount.value;
  if (amount === null || resetProblem.value || !resetAck.value) return;
  busy.value = 'practice-reset';
  practiceError.value = null;
  try {
    const res = await resetPractice(amount);
    practiceDone(t('practice.resetToast', { amount: usdc(res.dry_run_wallet) }), res.engineBack);
  } catch (e) {
    practiceError.value = controlErrorText(e);
  } finally {
    busy.value = null;
  }
}
/** The request went through once the engine restarts: close the dialog and show the calm waiting state. */
watch(restarting, (r) => {
  if (r) showReset.value = false;
});
</script>

<template>
  <div class="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-semibold text-balance text-highlighted">
          {{ t('wallet.title') }}
        </h1>
        <p class="mt-1 text-sm text-pretty text-muted">
          {{ t('wallet.subtitle') }}
        </p>
      </div>
      <UButton
        icon="i-mdi-refresh"
        color="neutral"
        variant="ghost"
        :loading="loading"
        :aria-label="t('common.refresh')"
        @click="refresh"
      />
    </div>

    <UAlert
      v-if="error"
      color="error"
      variant="subtle"
      icon="i-mdi-alert-circle-outline"
      :title="t('wallet.loadError')"
      :description="error"
    />
    <UAlert
      v-if="actionError"
      color="error"
      variant="subtle"
      icon="i-mdi-alert-circle-outline"
      :title="t('wallet.failed')"
      :description="actionError"
      :close="true"
      @update:open="actionError = null"
    />

    <!-- Current mode -->
    <div
      v-if="status"
      class="rounded-2xl border p-6"
      :class="
        live ? 'border-rose-500/50 bg-rose-500/10' : 'border-emerald-500/40 bg-emerald-500/10'
      "
    >
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-4">
          <div
            class="flex size-12 items-center justify-center rounded-2xl"
            :class="live ? 'bg-rose-500/20 text-rose-300' : 'bg-emerald-500/20 text-emerald-300'"
          >
            <UIcon :name="live ? 'i-mdi-cash-multiple' : 'i-mdi-school-outline'" class="size-7" />
          </div>
          <div>
            <div class="text-sm text-muted">{{ t('wallet.mode.using') }}</div>
            <div class="text-2xl font-semibold text-highlighted">
              {{ live ? t('common.realMoney') : t('common.practiceMoney') }}
            </div>
            <div v-if="live && status.capital" class="nova-money text-sm text-muted">
              {{ t('wallet.mode.upTo', { capital: status.capital }) }}
            </div>
            <div v-else-if="!live" class="text-sm text-muted">
              {{ t('wallet.mode.pretend') }}
            </div>
          </div>
        </div>
        <UButton
          v-if="live"
          size="lg"
          color="neutral"
          variant="outline"
          icon="i-mdi-school-outline"
          :loading="busy === 'paper'"
          :disabled="openTrades > 0"
          @click="doBackToPractice"
          >{{ t('wallet.mode.backToPractice') }}</UButton
        >
        <UButton
          v-else
          size="lg"
          color="primary"
          icon="i-mdi-cash-multiple"
          :disabled="step < 4"
          @click="openGoLive"
          >{{ t('wallet.mode.useReal') }}</UButton
        >
      </div>
      <p v-if="live && openTrades > 0" class="mt-3 text-sm text-muted">
        {{ t('wallet.mode.sellFirst', openTrades) }}
      </p>
      <p v-if="!live && step < 4" class="mt-3 text-sm text-muted">
        {{ t('wallet.mode.stepsLeft', 4 - step) }}
      </p>
    </div>

    <!-- Leverage: Sentinel may borrow up to 3x on new trades only when switched on (both modes) -->
    <NovaAiLeverage v-if="status" compact />

    <!-- Practice money (practice mode only) -->
    <NovaPanel
      v-if="status && !live"
      id="practice"
      class="scroll-mt-6"
      :title="t('common.practiceMoney')"
      :subtitle="t('practice.subtitle')"
    >
      <div
        v-if="practiceLoadError && !practiceInfo"
        class="flex flex-wrap items-center gap-3 text-sm text-muted"
      >
        <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
          <UIcon name="i-mdi-cloud-off-outline" class="size-5 text-muted" />
        </span>
        <span class="min-w-0 flex-1 text-pretty">{{ t('practice.loadError') }}</span>
        <UButton color="neutral" variant="outline" icon="i-mdi-refresh" @click="loadPractice">{{
          t('common.retry')
        }}</UButton>
      </div>
      <div v-else-if="!practiceInfo" class="flex flex-col gap-3">
        <USkeleton class="h-4 w-40 rounded-full" />
        <USkeleton class="h-10 w-56 rounded-xl" />
        <USkeleton class="h-4 w-72 rounded-full" />
      </div>
      <div v-else class="flex flex-col gap-6">
        <div>
          <div class="nova-label">{{ t('practice.putIn') }}</div>
          <div class="mt-1 flex flex-wrap items-baseline gap-x-2">
            <span
              class="nova-money text-4xl font-semibold tracking-tight text-highlighted sm:text-5xl"
              >{{ novaMoney(practiceNow, '', Number.isInteger(practiceNow) ? 0 : 2) }}</span
            >
            <span class="text-lg font-medium text-muted">USDC</span>
          </div>
          <p class="mt-2 text-sm text-pretty text-muted">
            <I18nT
              v-if="practiceStartedOn"
              keypath="practice.startedWithOn"
              tag="span"
              scope="global"
            >
              <template #amount
                ><span class="nova-money font-medium text-default">{{
                  usdc(practiceInfo.started_with)
                }}</span></template
              >
              <template #date>{{ practiceStartedOn }}</template>
            </I18nT>
            <I18nT v-else keypath="practice.startedWith" tag="span" scope="global">
              <template #amount
                ><span class="nova-money font-medium text-default">{{
                  usdc(practiceInfo.started_with)
                }}</span></template
              >
            </I18nT>
            <template v-if="practiceInfo.total_added > 0">
              {{ SPACE
              }}<I18nT keypath="practice.added" tag="span" scope="global">
                <template #amount
                  ><span class="nova-money font-medium text-default">{{
                    usdc(practiceInfo.total_added)
                  }}</span></template
                >
              </I18nT>
            </template>
            {{ t('practice.onTop') }}
          </p>
        </div>

        <!-- Restarting: calm waiting state -->
        <div
          v-if="practiceBusy"
          class="nova-tile flex items-start gap-3 p-4"
          role="status"
          aria-live="polite"
        >
          <span class="relative mt-1 flex size-3 shrink-0">
            <span
              class="absolute inline-flex size-full animate-ping rounded-full bg-secondary/60"
            />
            <span class="relative inline-flex size-3 rounded-full bg-secondary" />
          </span>
          <div class="min-w-0">
            <div class="font-semibold text-highlighted">
              {{ restarting ? t('practice.restartingTitle') : t('practice.savingTitle') }}
            </div>
            <p class="mt-1 text-sm text-pretty text-muted">
              {{ t('practice.waitText') }}
            </p>
          </div>
        </div>

        <!-- Add practice money -->
        <div v-else class="flex flex-col gap-3">
          <h3 class="text-sm font-semibold text-highlighted">{{ t('practice.addTitle') }}</h3>
          <div class="flex flex-wrap gap-2" role="group" :aria-label="t('practice.quickAmounts')">
            <button
              v-for="v in QUICK_ADD"
              :key="v"
              type="button"
              class="nova-num h-10 rounded-full border px-4 text-sm font-semibold transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
              :class="
                addAmount === v
                  ? 'border-primary/50 bg-primary/10 text-primary'
                  : 'border-default text-default hover:bg-accented/60'
              "
              :aria-pressed="addAmount === v"
              @click="addAmount = v"
            >
              +{{ usdc(v) }}
            </button>
          </div>
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start">
            <UFormField :error="!!addProblem" class="sm:w-56">
              <UInputNumber
                v-model="addAmount"
                size="lg"
                :step="100"
                :step-snapping="false"
                :placeholder="t('practice.otherAmount')"
                :aria-label="t('practice.amountAria')"
                class="w-full"
              />
            </UFormField>
            <UButton
              size="lg"
              color="primary"
              icon="i-mdi-plus"
              class="justify-center rounded-xl font-semibold whitespace-normal"
              variant="solid"
              :disabled="!!addProblem"
              @click="doAddPractice"
              >{{ t('practice.addButton') }}</UButton
            >
          </div>
          <p v-if="addProblem" class="text-sm text-pretty text-error" role="alert">
            {{ addProblem }}
          </p>
          <UAlert
            v-if="practiceError && !showReset"
            color="error"
            variant="subtle"
            icon="i-mdi-alert-circle-outline"
            :title="t('wallet.failed')"
            :description="practiceError"
            :close="true"
            @update:open="practiceError = null"
          />
        </div>

        <div
          v-if="!practiceBusy"
          class="flex flex-wrap items-center justify-between gap-3 border-t border-default/50 pt-4"
        >
          <p class="text-sm text-pretty text-muted">{{ t('practice.cleanSlate') }}</p>
          <UButton color="neutral" variant="ghost" icon="i-mdi-restore" @click="openReset">{{
            t('practice.startOver')
          }}</UButton>
        </div>
      </div>
    </NovaPanel>
    <p v-else-if="status && live" id="practice" class="px-1 text-sm text-pretty text-muted">
      {{ t('wallet.liveNoPractice') }}
    </p>

    <!-- Steps -->
    <div v-if="status && !live" class="flex flex-col gap-3">
      <!-- 1 connect -->
      <div class="nova-panel flex items-start gap-4 rounded-2xl p-5">
        <div
          class="flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
          :class="
            step > 1 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-brand-400/20 text-brand-300'
          "
        >
          <UIcon v-if="step > 1" name="i-mdi-check" class="size-5" /><span v-else>1</span>
        </div>
        <div class="flex-1">
          <h2 class="font-semibold text-highlighted">{{ t('wallet.connect.title') }}</h2>
          <p v-if="connectedAddr" class="mt-1 text-muted">
            <I18nT keypath="wallet.connect.connected" tag="span" scope="global">
              <template #address
                ><span class="font-mono text-default">{{ short(connectedAddr) }}</span></template
              >
            </I18nT>
            <button
              v-if="wallet?.address"
              type="button"
              class="ms-3 text-sm text-dimmed underline hover:text-default"
              @click="doForget"
            >
              {{ t('wallet.connect.disconnect') }}
            </button>
          </p>
          <template v-else>
            <p class="mt-1 text-muted">
              {{ t('wallet.connect.why') }}
            </p>
            <div class="mt-3">
              <UButton
                v-if="hasMetaMask"
                size="lg"
                icon="i-mdi-wallet-outline"
                :loading="busy === 'connect'"
                @click="doConnect"
                >{{ t('wallet.connect.button') }}</UButton
              >
              <I18nT
                v-else
                keypath="wallet.connect.notFound"
                tag="p"
                scope="global"
                class="text-sm text-muted"
              >
                <template #link
                  ><a
                    href="https://metamask.io/download/"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-brand-300 underline"
                    >metamask.io</a
                  ></template
                >
              </I18nT>
            </div>
          </template>
          <p v-if="walletMismatch" class="mt-2 text-sm text-brand-300">
            {{
              t('wallet.connect.mismatch', {
                account: short(account),
                wallet: short(wallet?.address),
              })
            }}
          </p>
        </div>
      </div>

      <!-- 2 fund -->
      <div
        class="nova-panel flex items-start gap-4 rounded-2xl p-5"
        :class="{ 'opacity-60': step < 2 }"
      >
        <div
          class="flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
          :class="
            step > 2 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-brand-400/20 text-brand-300'
          "
        >
          <UIcon v-if="step > 2" name="i-mdi-check" class="size-5" /><span v-else>2</span>
        </div>
        <div class="flex-1">
          <h2 class="font-semibold text-highlighted">{{ t('wallet.fund.title') }}</h2>
          <p class="mt-1 text-muted">
            {{ t('wallet.fund.text', { min: minCapital }) }}
          </p>
          <I18nT
            v-if="balanceInfo"
            keypath="wallet.fund.balance"
            tag="p"
            scope="global"
            class="mt-2 text-default"
          >
            <template #balance
              ><span class="nova-money font-semibold">{{
                novaMoney(balance, 'USDC')
              }}</span></template
            >
          </I18nT>
          <p v-if="balanceInfo?.error" class="mt-1 text-sm text-rose-300">
            {{ balanceInfo.error }}
          </p>
          <UButton
            class="mt-3"
            color="neutral"
            variant="outline"
            icon="i-mdi-open-in-new"
            to="https://app.hyperliquid.xyz/portfolio"
            target="_blank"
            >{{ t('wallet.fund.open') }}</UButton
          >
        </div>
      </div>

      <!-- 3 approve -->
      <div
        class="nova-panel flex items-start gap-4 rounded-2xl p-5"
        :class="{ 'opacity-60': step < 3 }"
      >
        <div
          class="flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
          :class="
            step > 3 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-brand-400/20 text-brand-300'
          "
        >
          <UIcon v-if="step > 3" name="i-mdi-check" class="size-5" /><span v-else>3</span>
        </div>
        <div class="flex-1">
          <h2 class="font-semibold text-highlighted">{{ t('wallet.approve.title') }}</h2>
          <I18nT keypath="wallet.approve.text" tag="p" scope="global" class="mt-1 text-muted">
            <template #buySell
              ><b class="text-default">{{ t('wallet.approve.buySell') }}</b></template
            >
            <template #noWithdraw
              ><b class="text-default">{{ t('wallet.approve.noWithdraw') }}</b></template
            >
          </I18nT>
          <p v-if="step > 3" class="mt-2 text-sm text-emerald-300">
            {{ t('wallet.approve.done', { address: short(wallet?.address) }) }}
          </p>
          <UButton
            v-else
            class="mt-3"
            size="lg"
            icon="i-mdi-draw-pen"
            :disabled="step < 3 || !hasMetaMask"
            :loading="busy === 'approve'"
            @click="doApprove"
            >{{ t('wallet.approve.sign') }}</UButton
          >
        </div>
      </div>

      <p class="px-1 text-sm text-muted">
        {{ t('wallet.practised', soldCount) }}
        <template v-if="soldCount < 30">{{ t('wallet.tooFew') }}</template>
      </p>
    </div>

    <!-- Go live -->
    <UModal
      v-model:open="showGoLive"
      :title="t('wallet.goLive.title')"
      :ui="{ content: 'max-w-lg' }"
    >
      <template #body>
        <div class="flex flex-col gap-4 text-left">
          <UFormField
            :label="t('wallet.goLive.amountLabel')"
            :help="t('wallet.goLive.amountHelp', { min: minCapital, max: balance.toFixed(2) })"
          >
            <UInputNumber
              v-model="capital"
              :min="minCapital"
              :max="Math.floor(balance)"
              :step="10"
              class="w-full"
            />
          </UFormField>
          <div class="flex flex-col gap-2">
            <UCheckbox v-model="ack.lose" :label="t('wallet.goLive.ackLose')" />
            <UCheckbox v-model="ack.noGuarantee" :label="t('wallet.goLive.ackNoGuarantee')" />
            <UCheckbox
              v-model="ack.leverage"
              :label="
                botSettings?.ai_leverage
                  ? t('wallet.goLive.ackLeverageOn')
                  : t('wallet.goLive.ackLeverageOff')
              "
            />
          </div>
          <UFormField :label="t('wallet.goLive.typePhrase', { phrase })">
            <UInput v-model="typed" :placeholder="phrase" class="w-full" autocomplete="off" />
          </UFormField>
          <p class="text-sm text-muted">
            {{ t('wallet.goLive.note') }}
          </p>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton color="neutral" variant="ghost" @click="showGoLive = false">{{
            t('common.cancel')
          }}</UButton>
          <UButton
            color="error"
            icon="i-mdi-cash-multiple"
            :disabled="!canGoLive"
            :loading="busy === 'live'"
            @click="doGoLive"
            >{{ t('wallet.goLive.start') }}</UButton
          >
        </div>
      </template>
    </UModal>

    <!-- Start practice over -->
    <UModal
      v-model:open="showReset"
      :title="t('practice.reset.title')"
      :ui="{ content: 'max-w-lg' }"
    >
      <template #body>
        <div class="flex flex-col gap-4 text-left">
          <p class="text-sm text-pretty text-muted">
            {{ t('practice.reset.text') }}
          </p>
          <UFormField :label="t('practice.reset.startWith')" :error="resetProblem ?? false">
            <UInputNumber
              v-model="resetAmount"
              size="lg"
              :step="100"
              :step-snapping="false"
              :placeholder="t('practice.reset.amountPlaceholder')"
              class="w-full"
            />
          </UFormField>
          <UCheckbox v-model="resetAck" :label="t('practice.reset.ack')" />
          <UAlert
            v-if="practiceError"
            color="error"
            variant="subtle"
            icon="i-mdi-alert-circle-outline"
            :title="t('wallet.failed')"
            :description="practiceError"
          />
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton color="neutral" variant="ghost" @click="showReset = false">{{
            t('common.cancel')
          }}</UButton>
          <UButton
            color="primary"
            variant="solid"
            icon="i-mdi-restore"
            :disabled="!resetAck || !!resetProblem"
            :loading="busy === 'practice-reset'"
            @click="doResetPractice"
            >{{ t('practice.startOver') }}</UButton
          >
        </div>
      </template>
    </UModal>
  </div>
</template>
