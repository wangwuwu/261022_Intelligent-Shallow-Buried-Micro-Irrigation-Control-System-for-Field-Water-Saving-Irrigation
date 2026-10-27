<script setup>
defineProps({ label: String, error: String, required: Boolean, hideRequiredMarker: Boolean });
</script>
<template>
  <label class="form-field"
    ><span v-if="label" class="form-field-label"
      >{{ label }}<span v-if="required && !hideRequiredMarker" class="required"> *</span></span
    ><slot /><span v-if="error" class="error-text" role="alert">{{
      error
    }}</span></label
  >
</template>
