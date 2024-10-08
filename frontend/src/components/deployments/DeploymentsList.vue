<template>
  <div class="table-list px-5 table-scrollable-div">
    <b-container
      fluid
      class="px-0"
    >
      <b-skeleton-wrapper
        :loading="loading"
        class="pb-1 pt-4 justify-content-start"
      >
        <template #loading>
          <b-col>
            <list-item-skeleton class="mb-2" />
            <list-item-skeleton class="mb-2" />
            <list-item-skeleton class="mb-2" />
            <list-item-skeleton class="mb-2" />
          </b-col>
        </template>
        <!-- Filter -->
        <b-row class="mt-2">
          <b-col
            cols="8"
            md="6"
            lg="4"
            xl="4"
          >
            <b-input-group size="sm">
              <b-form-input
                id="filter-input"
                v-model="filter"
                type="search"
                :placeholder="$t('forms.filter-placeholder')"
              />
              <b-input-group-append>
                <b-button
                  :disabled="!filter"
                  @click="filter = ''"
                >
                  {{ $t('forms.clear') }}
                </b-button>
              </b-input-group-append>
            </b-input-group>
          </b-col>
          <b-row
            class="ml-auto mr-2"
          >
            <b-col>
              <b-form-group
                :label="$t('forms.show-pages')"
                label-for="per-page-select"
                label-cols-md="5"
                label-align-sm="right"
                class="text-medium-gray mr-2 mr-lg-0"
              >
                <b-form-select
                  id="per-page-select"
                  v-model="perPage"
                  :label="$t('forms.show-pages')"
                  :options="pageOptions"
                  size="sm"
                />
              </b-form-group>
            </b-col>
            <b-col>
              <b-pagination
                v-model="currentPage"
                :total-rows="totalRows"
                :per-page="perPage"
                aria-controls="deployments-table"
                size="sm"
              />
            </b-col>
          </b-row>
        </b-row>

        <b-row>
          <b-col
            cols="12"
            class="d-flex flex-row flex-wrap justify-content-start"
          >
            <b-table
              id="deployments-table"
              :items="deployments"
              :fields="fields"
              :responsive="true"
              :per-page="perPage"
              :current-page="currentPage"
              :filter="filter"
              :filter-included-fields="filterOn"
              :tbody-tr-class="rowClass"
              @filtered="onFiltered"
              @row-clicked="redirectDeployment"
            >
              <template #cell(visible)="data">
                <p class="text-dark-gray m-0 text-center">
                  <b-badge :variant="data.item.visible ? 'success' : 'danger'">
                    {{ data.item.visible ? $t('views.deployment.visibility.visible') : $t('views.deployment.visibility.not-visible') }}
                  </b-badge>
                </p>
              </template>
              <template #cell(name)="data">
                <p class="m-0 font-weight-bold">
                  {{ data.item.name }}
                </p>
              </template>
              <template #cell(description)="data">
                <p class="text-dark-gray m-0">
                  {{ data.item.description }}
                </p>
              </template>
              <template #cell(startedDesktops)="data">
                <p class="text-dark-gray m-0">
                  {{ data.item.startedDesktops }} / {{ data.item.totalDesktops }}
                </p>
              </template>
              <template #cell(actions)="data">
                <div class="d-flex justify-content-center align-items-center">
                  <b-button
                    class="rounded-circle btn btn-red px-2 mr-2"
                    :title="$t('components.statusbar.deployment.buttons.delete.title')"
                    @click="deleteDeployment(data.item)"
                  >
                    <b-icon
                      icon="trash-fill"
                      scale="0.75"
                    />
                  </b-button>
                  <b-button
                    v-if="data.item.needsBooking"
                    class="rounded-circle btn-orange px-2 mr-2"
                    @click="onClickBookingDesktop(data.item)"
                  >
                    <b-icon
                      icon="calendar"
                      scale="0.75"
                    />
                  </b-button>
                </div>
              </template>
            </b-table>
            <b-row
              class="ml-auto mr-2"
            >
              <b-col>
                <b-form-group
                  :label="$t('forms.show-pages')"
                  label-for="per-page-select"
                  label-cols-md="5"
                  label-align-sm="right"
                  class="text-medium-gray mr-2 mr-lg-0"
                >
                  <b-form-select
                    id="per-page-select"
                    v-model="perPage"
                    :label="$t('forms.show-pages')"
                    :options="pageOptions"
                    size="sm"
                  />
                </b-form-group>
              </b-col>
              <b-col>
                <b-pagination
                  v-model="currentPage"
                  :total-rows="totalRows"
                  :per-page="perPage"
                  aria-controls="deployments-table"
                  size="sm"
                />
              </b-col>
            </b-row>
          </b-col>
        </b-row>
      </b-skeleton-wrapper>
    </b-container>
  </div>
</template>
<script>
import i18n from '@/i18n'
import ListItemSkeleton from '@/components/ListItemSkeleton.vue'
import { ref, reactive, watch } from '@vue/composition-api'

export default {
  components: { ListItemSkeleton },
  props: {
    deployments: {
      required: true,
      type: Array
    },
    loading: {
      required: true,
      type: Boolean
    }
  },
  setup (props, context) {
    const $store = context.root.$store
    const perPage = ref(10)
    const pageOptions = ref([10, 20, 30, 50, 100])
    const currentPage = ref(1)
    const totalRows = ref(1)
    const filter = ref('')
    const filterOn = reactive(['name', 'description', 'desktopName', 'template'])

    const onFiltered = (filteredItems) => {
      // Trigger pagination to update the number of buttons/pages due to filtering
      totalRows.value = filteredItems.length
      currentPage.value = 1
    }

    watch(() => props.deployments, (newVal) => {
      totalRows.value = newVal.length
    })

    const rowClass = (item, type) => {
      if (item && type === 'row') {
        if (item.visible === true) {
          return 'cursor-pointer visibleHighlight'
        } else {
          return 'cursor-pointer'
        }
      } else {
        return null
      }
    }

    const redirectDeployment = (item) => {
      context.root.$router.push({ name: 'deployment_desktops', params: { id: item.id } })
    }

    const deleteDeployment = (deployment) => {
      context.root.$snotify.clear()

      const yesAction = () => {
        context.root.$snotify.clear()
        $store.dispatch('deleteDeployment', { id: deployment.id })
      }

      const noAction = (toast) => {
        context.root.$snotify.clear()
      }

      context.root.$snotify.prompt(`${i18n.t('messages.confirmation.delete-deployment', { name: deployment.name })}`, {
        position: 'centerTop',
        buttons: [
          { text: `${i18n.t('messages.yes')}`, action: yesAction, bold: true },
          { text: `${i18n.t('messages.no')}`, action: noAction }
        ],
        placeholder: ''
      })
    }

    const onClickBookingDesktop = (deployment) => {
      const data = { id: deployment.id, type: 'deployment', name: deployment.name }
      $store.dispatch('goToItemBooking', data)
    }

    watch(() => props.desktops, (newVal) => {
      totalRows.value = newVal.length
    })

    return {
      rowClass,
      redirectDeployment,
      deleteDeployment,
      onClickBookingDesktop,
      onFiltered,
      filter,
      filterOn,
      perPage,
      pageOptions,
      currentPage,
      totalRows
    }
  },
  data () {
    return {
      fields: [
        {
          key: 'visible',
          sortable: true,
          label: i18n.t('views.deployments.table-header.visible'),
          thStyle: { width: '5%' }
        },
        {
          key: 'name',
          sortable: true,
          label: i18n.t('views.deployments.table-header.name'),
          thStyle: { width: '20%' },
          tdClass: 'name'
        },
        {
          key: 'description',
          sortable: true,
          label: i18n.t('views.deployments.table-header.description'),
          thStyle: { width: '20%' },
          tdClass: 'name'
        },
        {
          key: 'desktopName',
          sortable: true,
          label: i18n.t('views.deployments.table-header.desktop-name'),
          thStyle: { width: '20%' },
          tdClass: 'name'
        },
        {
          key: 'template',
          sortable: true,
          label: i18n.t('views.deployments.table-header.template'),
          thStyle: { width: '20%' },
          tdClass: 'name'
        },
        {
          key: 'startedDesktops',
          sortable: true,
          label: i18n.t('views.deployments.table-header.started-desktops'),
          thStyle: { width: '35%' }
        },
        {
          key: 'actions',
          label: i18n.t('views.deployments.table-header.actions'),
          thStyle: { width: '5%' }
        }
      ]
    }
  }
}
</script>
