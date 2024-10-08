<template>
  <b-container
    fluid
    class="main-container pl-3 pr-3 pl-xl-5 pr-xl-5 pb-5"
  >
    <b-form @submit.prevent="submitForm">
      <!-- Title -->
      <b-row clas="mt-2">
        <h4 class="p-1 mb-4 mt-2 mt-xl-4 ml-2">
          <strong>{{ $t('forms.new-template.title') }}</strong>
        </h4>
      </b-row>

      <!-- Name -->
      <b-row>
        <b-col
          cols="4"
          xl="2"
        >
          <label for="name">{{ $t('forms.new-template.name') }}</label>
        </b-col>
        <b-col
          cols="6"
          xl="4"
          class="mb-4"
        >
          <b-form-input
            id="name"
            v-model="name"
            type="text"
            size="sm"
            maxlength="40"
            :state="v$.name.$error ? false : null"
            @blur="v$.name.$touch"
          />
          <b-form-invalid-feedback
            v-if="v$.name.$error"
            id="nameError"
          >
            {{ $t(`validations.${v$.name.$errors[0].$validator}`, { property: $t('forms.new-template.name'), model: name.length, min: 4, max: 40 }) }}
          </b-form-invalid-feedback>
        </b-col>
      </b-row>

      <!-- Description -->
      <b-row class="mt-4">
        <b-col
          cols="4"
          xl="2"
        >
          <label for="description">{{ $t('forms.new-template.description') }}</label>
        </b-col>
        <b-col
          cols="6"
          xl="4"
        >
          <b-form-input
            id="description"
            v-model="description"
            type="text"
            size="sm"
          />
        </b-col>
      </b-row>

      <!-- Enabled -->
      <b-row>
        <b-col cols="12">
          <div class="d-flex">
            <label
              for="switch_1"
              class="mr-2"
            ><b-icon
              icon="eye-slash-fill"
              class="mr-2"
              variant="danger"
            />{{ $t('forms.new-template.disabled') }}</label>
            <b-form-checkbox
              id="checkbox-1"
              v-model="enabled"
              switch
            >
              <b-icon
                class="mr-2"
                icon="eye-fill"
                variant="success"
              />{{ $t('forms.new-template.enabled') }}
            </b-form-checkbox>
          </div>
        </b-col>
      </b-row>

      <b-row clas="mt-2">
        <h4 class="p-1 mb-2 mt-2 mt-xl-4 ml-2">
          <strong>{{ $t('forms.allowed.title') }}</strong>
        </h4>
      </b-row>

      <!-- Allowed -->
      <AllowedForm />

      <!-- Buttons -->
      <b-row align-h="end">
        <b-button
          size="md"
          class="btn-red rounded-pill mt-4 mr-2"
          @click="navigate('desktops')"
        >
          {{ $t('forms.cancel') }}
        </b-button>
        <b-button
          type="submit"
          size="md"
          class="btn-green rounded-pill mt-4 ml-2 mr-5"
        >
          {{ $t('forms.create') }}
        </b-button>
      </b-row>
    </b-form>
  </b-container>
</template>

<script>
import { ref, computed, onUnmounted, onMounted } from '@vue/composition-api'
import useVuelidate from '@vuelidate/core'
import { required, maxLength, minLength } from '@vuelidate/validators'
import AllowedForm from '@/components/AllowedForm.vue'
import { map } from 'lodash'

const inputFormat = value => /^[-_àèìòùáéíóúñçÀÈÌÒÙÁÉÍÓÚÑÇ .a-zA-Z0-9]+$/.test(value)

export default {
  components: {
    AllowedForm
  },
  setup (props, context) {
    const $store = context.root.$store
    const navigate = (path) => {
      $store.dispatch('navigate', path)
    }
    onMounted(() => {
      if (templateNewItemId.value.length < 1) {
        $store.dispatch('navigate', 'desktops')
      }
    })

    const name = ref('')
    const description = ref('')
    const enabled = ref(true)

    const groupsChecked = computed(() => $store.getters.getGroupsChecked)
    const selectedGroups = computed(() => $store.getters.getSelectedGroups)
    const usersChecked = computed(() => $store.getters.getUsersChecked)
    const selectedUsers = computed(() => $store.getters.getSelectedUsers)
    const templateNewItemId = computed(() => $store.getters.getTemplateNewItemId)
    const v$ = useVuelidate({
      name: {
        required,
        maxLengthValue: maxLength(40),
        minLengthValue: minLength(4),
        inputFormat
      }
    }, { name })

    const submitForm = () => {
      // Check if the form is valid
      v$.value.$touch()
      if (v$.value.$invalid) {
        document.getElementById(v$.value.$errors[0].$property).focus()
        return
      }
      const groups = groupsChecked.value ? map(selectedGroups.value, 'id') : false
      const users = usersChecked.value ? map(selectedUsers.value, 'id') : false
      $store.dispatch('createNewTemplate',
        {
          desktop_id: templateNewItemId.value,
          name: name.value,
          description: description.value,
          allowed: {
            users,
            groups
          },
          enabled: enabled.value
        }
      )
    }

    onUnmounted(() => {
      $store.dispatch('resetAllowedState')
    })

    return {
      name,
      description,
      enabled,
      groupsChecked,
      selectedGroups,
      usersChecked,
      selectedUsers,
      v$,
      submitForm,
      navigate
    }
  }
}
</script>
