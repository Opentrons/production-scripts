<template>
  <div class="locale-switcher" :class="`is-${variant}`" role="group" :aria-label="t('locale.label')">
    <button
      type="button"
      :class="{ 'is-active': locale === 'zh-CN' }"
      :aria-pressed="locale === 'zh-CN'"
      @click="setLocale('zh-CN')"
    >
      {{ t('locale.chinese') }}
    </button>
    <button
      type="button"
      :class="{ 'is-active': locale === 'en-US' }"
      :aria-pressed="locale === 'en-US'"
      @click="setLocale('en-US')"
    >
      EN
    </button>
  </div>
</template>

<script setup lang="ts">
import { useAppLocale } from '@/i18n'

withDefaults(defineProps<{ variant?: 'light' | 'dark' | 'surface' }>(), {
  variant: 'light',
})

const { locale, setLocale, t } = useAppLocale()
</script>

<style scoped>
.locale-switcher {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px;
  padding: 2px;
  border: 1px solid #d9e0e4;
  border-radius: 999px;
  background: #f4f7f8;
}

.locale-switcher button {
  min-width: 40px;
  height: 26px;
  padding: 0 9px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: #66737a;
  font-size: 10px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color .16s, color .16s, box-shadow .16s;
}

.locale-switcher button:hover {
  color: #17212d;
}

.locale-switcher button.is-active {
  background: #fff;
  color: #087b91;
  box-shadow: 0 1px 3px rgba(24, 38, 46, 0.12);
}

.locale-switcher.is-dark {
  border-color: rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
}

.locale-switcher.is-dark button {
  color: rgba(255, 255, 255, 0.7);
}

.locale-switcher.is-dark button:hover,
.locale-switcher.is-dark button.is-active {
  color: #fff;
}

.locale-switcher.is-dark button.is-active {
  background: rgba(255, 255, 255, 0.16);
  box-shadow: none;
}

.locale-switcher.is-surface {
  background: rgba(255, 255, 255, 0.86);
}
</style>
