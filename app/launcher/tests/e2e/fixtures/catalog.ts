import type {
  CatalogAssetDetail,
  CatalogMetadata,
  CatalogTreeNode,
  LauncherHomeResponse,
} from '../../../src/types'

type CatalogFixtures = {
  home: LauncherHomeResponse
  metadata: CatalogMetadata
  catalogAssetsResponse: {
    count: number
    assets: CatalogAssetDetail[]
    tree: CatalogTreeNode[]
  }
  assetDetail: CatalogAssetDetail
}

export function createCatalogFixtures(): CatalogFixtures {
  const assetDetail: CatalogAssetDetail = {
    asset_id: 'entity.everyday_banking_graph',
    asset_type: 'entity',
    version: '1.0.0',
    name: 'Everyday Banking Graph',
    status: 'draft',
    primary_kb: 'business_model_kb',
    domain_id: 'asset-management',
    module_id: 'asset-catalog',
    tags: [],
    stores: ['repository'],
    payload: {
      entities: [
        {
          id: 'entity.customer',
          name: 'Customer',
          layer: 'capability',
          role: 'core',
          description: 'Customer profile entity',
          aliases: ['cliente'],
          attributes: [],
        },
        {
          id: 'entity.account',
          name: 'SmartBalance Checking',
          layer: 'offering',
          role: 'experience',
          description: 'Deposits offering',
          aliases: [],
          attributes: [],
        },
      ],
      relations: [
        {
          id: 'relation.supports_account',
          source_entity_id: 'entity.customer',
          target_entity_id: 'entity.account',
          relation_type: 'supports',
          description: 'Customer supports SmartBalance Checking adoption',
        },
      ],
      layout: {
        nodes: {
          'entity.customer': { x: 120, y: 80 },
          'entity.account': { x: 420, y: 240 },
        },
      },
    },
    relations: [],
    relationships: [],
    asset_set_id: null,
    asset_set_version: null,
    checksum: 'fixture',
    active: false,
    active_environment: null,
  }

  const tree: CatalogTreeNode[] = [
    {
      id: 'kb:business_model_kb',
      label: 'business_model_kb',
      kind: 'knowledge_base',
      children: [
        {
          id: 'asset:entity.everyday_banking_graph',
          label: 'Everyday Banking Graph',
          kind: 'asset',
          asset_id: assetDetail.asset_id,
          asset_type: assetDetail.asset_type,
          version: assetDetail.version,
          status: assetDetail.status,
          tags: [],
          active: false,
          children: [],
        },
      ],
    },
  ]

  const metadata: CatalogMetadata = {
    environment: 'dev',
    asset_types: ['entity'],
    knowledge_bases: ['business_model_kb'],
    statuses: ['draft', 'ready_for_review', 'active'],
    tags: [],
    domains: ['asset-management'],
    modules: ['asset-catalog'],
  }

  return {
    home: {
      modules: [],
      featured_flows: [],
      recent_flows: [],
      navigation: { domains: [] },
    },
    metadata,
    catalogAssetsResponse: {
      count: 1,
      assets: [assetDetail],
      tree,
    },
    assetDetail,
  }
}
