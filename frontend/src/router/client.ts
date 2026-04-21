interface RouteInfo {
  name: string
  path: string
}

export interface RouteRecordRawRebuild extends RouteInfo {
  component: () => Promise<any>
}

export interface NavItem {
  googleIcon?: string
  name: string
  routeData: RouteRecordRawRebuild
}

export const defaultRoutes: NavItem[] = [
  {
    googleIcon: 'team_dashboard',
    name: '概览',
    routeData: {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard/DashboardIndex.vue')
    }
  },
  {
    googleIcon: 'deployed_code',
    name: '实例选择',
    routeData: {
      path: '/instances',
      name: 'Instances',
      component: () => import('@/views/Instances/InstanceSelectIndex.vue')
    }
  },
  {
    googleIcon: 'settings_applications',
    name: '实例操作',
    routeData: {
      path: '/operation',
      name: 'Operation',
      component: () => import('@/views/Operation/OperationIndex.vue')
    }
  },
  {
    googleIcon: 'terminal',
    name: '终端',
    routeData: {
      path: '/terminal',
      name: 'Terminal',
      component: () => import('@/views/Terminal/TerminalIndex.vue')
    }
  },
  {
    googleIcon: 'extension',
    name: '拓展商店',
    routeData: {
      path: '/store',
      name: 'Store',
      component: () => import('@/views/Store/StoreIndex.vue')
    }
  },
  {
    googleIcon: 'power',
    name: '拓展管理',
    routeData: {
      path: '/extension',
      name: 'ExtensionManage',
      component: () => import('@/views/ExtensionManage/ExtensionManageIndex.vue')
    }
  },
  {
    googleIcon: 'settings',
    name: '实例设置',
    routeData: {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/Settings/SettingsIndex.vue')
    }
  },
  {
    googleIcon: 'folder',
    name: '文件管理',
    routeData: {
      path: '/file-manager',
      name: 'FileManager',
      component: () => import('@/views/FileManager/FileManagerIndex.vue')
    }
  },
  {
    googleIcon: 'shield_lock',
    name: '安全设置',
    routeData: {
      path: '/security-settings',
      name: 'SecuritySettings',
      component: () => import('@/views/Settings/SecuritySettingsIndex.vue')
    }
  },
  {
    googleIcon: 'restore_page',
    name: '备份恢复',
    routeData: {
      path: '/backup-restore',
      name: 'BackupRestore',
      component: () => import('@/views/Settings/BackupRestoreIndex.vue')
    }
  },
  {
    googleIcon: 'receipt_long',
    name: '全局日志',
    routeData: {
      path: '/global-logs',
      name: 'GlobalLogs',
      component: () => import('@/views/Logs/GlobalLogIndex.vue')
    }
  },
  {
    googleIcon: 'vpn_key',
    name: '全局代理',
    routeData: {
      path: '/proxy-settings',
      name: 'ProxySettings',
      component: () => import('@/views/Settings/ProxySettingsIndex.vue')
    }
  },
  {
    googleIcon: 'lan',
    name: '实例代理',
    routeData: {
      path: '/instance-proxy',
      name: 'InstanceProxySettings',
      component: () => import('@/views/Settings/InstanceProxySettingsIndex.vue')
    }
  }
]
