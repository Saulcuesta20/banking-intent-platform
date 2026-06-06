import type { LauncherHomeResponse } from './types'

export function mergeHomeResponses(primary: LauncherHomeResponse, secondary?: LauncherHomeResponse): LauncherHomeResponse {
  if (!secondary) return primary

  const moduleMap = new Map(primary.modules.map((module) => [module.module_id, module]))
  for (const module of secondary.modules) {
    if (!moduleMap.has(module.module_id)) moduleMap.set(module.module_id, module)
  }

  const flowMap = new Map(primary.featured_flows.map((flow) => [flow.flow_id, flow]))
  for (const flow of [...secondary.featured_flows, ...secondary.recent_flows]) {
    if (!flowMap.has(flow.flow_id)) flowMap.set(flow.flow_id, flow)
  }

  return {
    modules: [...moduleMap.values()],
    featured_flows: [...flowMap.values()],
    recent_flows: [],
    navigation: {
      ...secondary.navigation,
      ...primary.navigation,
    },
  }
}
