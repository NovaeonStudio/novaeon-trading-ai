<script setup lang="ts">
import type { AuthPayload, AuthStorageWithBotId } from '@/types';

import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';

const props = withDefaults(
  defineProps<{
    inModal?: boolean;
    existingAuth?: AuthStorageWithBotId;
  }>(),
  {
    inModal: false,
    existingAuth: undefined,
  },
);
const emit = defineEmits<{ loginResult: [value: boolean] }>();
const { t } = useI18n();

const defaultURL = window.location.origin || 'http://localhost:3000';

const router = useRouter();
const route = useRoute();
const botStore = useBotStore();

const nameState = ref<boolean>();
const pwdState = ref<boolean>();
const urlState = ref<boolean>();
const errorMessage = ref<string>('');
const errorMessageCORS = ref<boolean>(false);
const formRef = ref<HTMLFormElement>();
const botEdit = ref<boolean>(false);
/** Visual only: shows a loading state on the connect button while the login request runs. */
const submitting = ref<boolean>(false);
const auth = ref<AuthPayload>({
  botName: '',
  url: defaultURL,
  username: '',
  password: '',
});

function emitLoginResult(value: boolean) {
  emit('loginResult', value);
}

const urlDuplicate = computed<boolean>(() => {
  const bots = Object.values(botStore.availableBots).find((bot) => bot.botUrl === auth.value.url);
  return !botEdit.value && bots !== undefined;
});

function checkFormValidity() {
  const valid = formRef.value?.checkValidity();
  nameState.value = valid || auth.value.username !== '';
  pwdState.value = valid || auth.value.password !== '';
  urlState.value = valid || auth.value.url !== '';
  return valid;
}

function resetLogin() {
  auth.value.botName = '';
  auth.value.url = defaultURL;
  auth.value.username = '';
  auth.value.password = '';
  nameState.value = undefined;
  pwdState.value = undefined;
  urlState.value = undefined;
  errorMessage.value = '';
  botEdit.value = false;
}

function handleReset(evt) {
  evt.preventDefault();
  resetLogin();
}

async function handleSubmit() {
  // Exit when the form isn't valid
  if (!checkFormValidity()) {
    return;
  }
  errorMessage.value = '';
  submitting.value = true;
  // Push the name to submitted names
  try {
    const botId =
      botEdit.value && props.existingAuth ? props.existingAuth.botId : botStore.nextBotId;
    const { login } = useLoginInfo(botId);
    await login(auth.value);
    if (botEdit.value) {
      // Bot editing ...
      const thisBot = botStore.botStores[botId];
      if (thisBot) {
        thisBot.isBotLoggedIn = true;
        thisBot.isBotOnline = true;
      }
      // botStore.allRefreshFull();
      emitLoginResult(true);
    } else {
      // Add new bot
      const sortId = Object.keys(botStore.availableBots).length + 1;
      botStore.addBot({
        botName: auth.value.botName,
        botId,
        botUrl: auth.value.url,
        sortId: sortId,
      });
      // switch to newly added bot
      botStore.selectBot(botId);
      emitLoginResult(true);
      botStore.allRefreshFull();
    }

    if (props.inModal === false) {
      if (typeof route?.query.redirect === 'string') {
        const resolved = router.resolve({ path: route.query.redirect });
        if (resolved.name === '/[...path]') {
          router.push('/');
        } else {
          router.push(resolved.path);
        }
      } else {
        // NovaeonTradingAI: land on the Command Center after login
        router.push(localStorage.getItem('nova-mode') === 'pro' ? '/command' : '/home');
      }
    }
  } catch (error) {
    errorMessageCORS.value = false;
    // this.nameState = false;
    console.error(error);
    if (axios.isAxiosError(error) && error.response && error.response.status === 401) {
      nameState.value = false;
      pwdState.value = false;
      errorMessage.value = t('login.errorAuth');
    } else {
      urlState.value = false;
      errorMessage.value = t('login.errorUnreachable', {
        url: auth.value.url,
        pingUrl: `${auth.value.url}/api/v1/ping`,
      });
      if (auth.value.url !== window.location.origin) {
        errorMessageCORS.value = true;
      }
    }
    console.error(errorMessage.value);
    emitLoginResult(false);
  } finally {
    submitting.value = false;
  }
}

function handleOk(evt) {
  evt.preventDefault();
  handleSubmit();
}

function reset() {
  resetLogin();
  console.log('reset ', props.existingAuth);
  if (props.existingAuth) {
    botEdit.value = true;
    auth.value.botName = props.existingAuth.botName;
    auth.value.url = props.existingAuth.apiUrl;
    auth.value.username = props.existingAuth.username ?? '';
  }
}

defineExpose({
  reset,
});

onMounted(() => {
  reset();
});
</script>

<template>
  <form
    ref="formRef"
    novalidate
    class="flex flex-col gap-4 text-start"
    @submit.stop.prevent="handleSubmit"
    @reset="handleReset"
  >
    <UFormField
      :label="t('login.url')"
      :description="t('login.urlHint')"
      :error="urlState === false ? t('login.urlError') : undefined"
      required
    >
      <UInput
        id="url-input"
        v-model="auth.url"
        required
        trim
        type="url"
        autocomplete="url"
        placeholder="http://127.0.0.1:8080"
        class="w-full"
        @keydown.enter="handleOk"
      />
    </UFormField>
    <UAlert
      v-if="urlDuplicate"
      color="warning"
      variant="subtle"
      icon="i-mdi-alert-outline"
      :title="t('login.urlDuplicate')"
    />
    <UFormField
      :label="t('login.username')"
      :error="nameState === false ? t('login.usernameError') : undefined"
      required
    >
      <UInput
        v-model="auth.username"
        required
        autocomplete="username"
        :placeholder="t('login.username')"
        class="w-full"
        @keydown.enter="handleOk"
      />
    </UFormField>
    <UFormField
      :label="t('login.password')"
      :error="pwdState === false ? t('login.passwordError') : undefined"
      required
    >
      <UInput
        v-model="auth.password"
        required
        type="password"
        autocomplete="current-password"
        :placeholder="t('login.password')"
        class="w-full"
        @keydown.enter="handleOk"
      />
    </UFormField>
    <UFormField :label="t('login.botName')" :hint="t('login.optional')">
      <UInput
        v-model="auth.botName"
        :placeholder="t('login.botNamePlaceholder')"
        class="w-full"
        @keydown.enter="handleOk"
      />
    </UFormField>
    <UAlert
      v-if="errorMessage"
      class="whitespace-pre-line"
      color="error"
      variant="subtle"
      icon="i-mdi-alert-circle-outline"
      :title="t('login.errorTitle')"
    >
      <template #description>
        <p class="text-pretty">{{ errorMessage }}</p>
        <p v-if="errorMessageCORS" class="mt-2 text-pretty">
          {{ t('login.errorCors') }}
        </p>
      </template>
    </UAlert>
    <div class="flex flex-wrap items-center justify-end gap-2 pt-2">
      <UButton
        :label="t('login.clear')"
        color="neutral"
        variant="ghost"
        type="reset"
        class="me-auto"
      />
      <UButton
        v-if="inModal"
        :label="t('common.cancel')"
        color="neutral"
        variant="outline"
        type="button"
        @click="emitLoginResult(true)"
      />
      <UButton
        :label="t('login.connect')"
        color="primary"
        variant="solid"
        type="submit"
        icon="i-mdi-link-variant"
        :loading="submitting"
        class="px-4 font-semibold"
      />
    </div>
  </form>
</template>
