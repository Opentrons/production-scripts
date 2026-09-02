export type DashboardLocale = 'zh' | 'en'

interface ModuleCopy {
  name: string
  summary: string
}

interface DashboardMessages {
  languageLabel: string
  simulatingLabel: string
  simulatingOn: string
  simulatingOff: string
  simulatingEnabled: string
  simulatingDisabled: string
  simulatingUpdateFailed: string
  brandAria: string
  navigationAria: string
  nav: {
    productLineTests: string
    dataAutomationUpload: string
    deviceManagement: string
    testManagement: string
    dataManagement: string
    versionChecks: string
    sopDuroCheck: string
    ecnCheck: string
    engineeringChanges: string
    ecn: string
    contactLetters: string
    productionAgent: string
    downloads: string
  }
  status: {
    active: string
    ready: string
    planned: string
  }
  dashboard: {
    eyebrow: string
    title: string
    introduction: string
    openOperations: string
    viewModules: string
    modulesEyebrow: string
    modulesTitle: string
    operationsEyebrow: string
    operationsTitle: string
    developerEyebrow: string
    developerTitle: string
    currentVersion: string
    lastUpdated: string
    openModule: (name: string) => string
    comingSoon: string
    modules: {
      operations: ModuleCopy
      versions: ModuleCopy
      downloads: ModuleCopy
      agent: ModuleCopy
    }
    routes: {
      devices: string
      testCases: string
      data: string
      uploadRecords: string
      productManagement: string
      analysis: string
      messages: string
      settings: string
    }
  }
  downloads: {
    eyebrow: string
    title: string
    introduction: string
    newUpload: string
    projectCount: (count: number) => string
    refresh: string
    loading: string
    loadFailed: string
    retry: string
    emptyTitle: string
    emptyDescription: string
    createProject: string
    versionCount: (count: number) => string
    noProjectDescription: string
    noVersions: string
    noVersionNotes: string
    manageVersion: (version: string) => string
    downloadFile: string
    editVersion: string
    deleteVersion: string
    newVersionEyebrow: string
    editVersionEyebrow: string
    uploadTitle: string
    editTitle: string
    closeForm: string
    projectName: string
    projectNamePlaceholder: string
    projectNameHelp: string
    projectDescription: string
    projectDescriptionPlaceholder: string
    version: string
    versionPlaceholder: string
    selectFile: string
    versionNotes: string
    versionNotesPlaceholder: string
    removeSelectedFile: string
    uploading: (progress: number) => string
    saving: string
    cancel: string
    processing: string
    uploadAndCreate: string
    saveChanges: string
    requestFailed: (status: number) => string
    unknownServerError: string
    versionRequired: string
    projectRequired: string
    fileRequired: string
    uploadSucceeded: (version: string) => string
    uploadFailed: string
    uploadRequestFailed: (status: number) => string
    resourceServiceUnavailable: string
    updateSucceeded: string
    updateFailed: string
    deleteConfirmation: (version: string) => string
    deleteSucceeded: (version: string) => string
    deleteFailed: string
  }
}

export const dashboardMessages: Record<DashboardLocale, DashboardMessages> = {
  zh: {
    languageLabel: '界面语言',
    simulatingLabel: 'Simulating',
    simulatingOn: '开',
    simulatingOff: '关',
    simulatingEnabled: '已启用 Simulating（SQLite）',
    simulatingDisabled: '已关闭 Simulating（MongoDB）',
    simulatingUpdateFailed: '更新 Simulating 失败',
    brandAria: '打开生产测试',
    navigationAria: '生产测试导航',
    nav: {
      productLineTests: '产品线测试',
      dataAutomationUpload: '数据自动化上传',
      deviceManagement: '设备管理',
      testManagement: '测试管理',
      dataManagement: '数据管理',
      versionChecks: 'BOM版本',
      sopDuroCheck: 'SOP&DURO核对',
      ecnCheck: 'ECN核对',
      engineeringChanges: '工程变更',
      ecn: 'ECN',
      contactLetters: '联络函',
      productionAgent: '生产助手',
      downloads: '资源下载',
    },
    status: {
      active: '可用',
      ready: '就绪',
      planned: '规划中',
    },
    dashboard: {
      eyebrow: 'OPENTRONS 生产系统',
      title: '生产测试',
      introduction: '统一管理工厂数据、机器人操作、上传记录、分析流程和自动化入口。',
      openOperations: '数据自动化上传',
      viewModules: '查看功能模块',
      modulesEyebrow: '系统地图',
      modulesTitle: '生产功能模块',
      operationsEyebrow: '应用入口',
      operationsTitle: '生产操作',
      developerEyebrow: '开发工具',
      developerTitle: '开发者选项',
      currentVersion: '当前版本',
      lastUpdated: '最后更新时间',
      openModule: (name) => `打开${name}`,
      comingSoon: '即将推出',
      modules: {
        operations: {
          name: '生产操作',
          summary: '用于文件上传、机器人操作、数据分析、消息和产品跟踪的生产应用。',
        },
        versions: {
          name: '版本管理',
          summary: '管理 Duro 产品、SOP 分析、BOM 对比和定时版本工作流。',
        },
        downloads: {
          name: '资源下载',
          summary: '通过统一 API 管理带版本的生产文件和可下载资源。',
        },
        agent: {
          name: '生产智能助手',
          summary: '面向生产自动化、辅助操作和队列工作流的智能助手空间。',
        },
      },
      routes: {
        devices: '设备管理',
        testCases: '测试管理',
        data: '数据管理',
        uploadRecords: '上传记录',
        productManagement: '产品管理',
        analysis: '数据分析',
        messages: '消息中心',
        settings: '系统设置',
      },
    },
    downloads: {
      eyebrow: '文件资源库',
      title: '资源下载',
      introduction: '按项目和版本管理静态文件资源，所有上传信息都会保存在数据库中。',
      newUpload: '上传新版本',
      projectCount: (count) => `${count} 个资源项目`,
      refresh: '刷新',
      loading: '正在加载资源项目…',
      loadFailed: '无法读取文件资源',
      retry: '重试',
      emptyTitle: '还没有资源项目',
      emptyDescription: '点击右上角“上传新版本”，创建第一个项目和版本。',
      createProject: '创建资源项目',
      versionCount: (count) => `${count} 个版本`,
      noProjectDescription: '暂无项目描述',
      noVersions: '该项目还没有版本。',
      noVersionNotes: '暂无版本说明',
      manageVersion: (version) => `管理版本 ${version}`,
      downloadFile: '下载文件',
      editVersion: '修改版本信息',
      deleteVersion: '删除版本',
      newVersionEyebrow: '新建资源版本',
      editVersionEyebrow: '编辑版本',
      uploadTitle: '上传文件资源',
      editTitle: '修改版本信息',
      closeForm: '关闭表单',
      projectName: '项目名称',
      projectNamePlaceholder: '输入新项目名称，或从已有项目中选择',
      projectNameHelp: '可自定义项目名称，也可以选择已有项目并为它创建新版本。',
      projectDescription: '项目描述',
      projectDescriptionPlaceholder: '简单说明项目用途和资源内容',
      version: '版本号',
      versionPlaceholder: '例如：1.0.0',
      selectFile: '选择文件',
      versionNotes: '版本说明',
      versionNotesPlaceholder: '记录本版本的更新内容、使用说明或注意事项',
      removeSelectedFile: '移除已选文件',
      uploading: (progress) => `正在上传 ${progress}%`,
      saving: '正在保存…',
      cancel: '取消',
      processing: '处理中…',
      uploadAndCreate: '上传并创建版本',
      saveChanges: '保存修改',
      requestFailed: (status) => `请求失败 (${status})`,
      unknownServerError: '未知服务器错误',
      versionRequired: '请填写版本号。',
      projectRequired: '请填写或选择项目名称。',
      fileRequired: '请选择需要上传的文件。',
      uploadSucceeded: (version) => `版本 ${version} 已上传并保存。`,
      uploadFailed: '文件上传失败。',
      uploadRequestFailed: (status) => `上传失败 (${status})`,
      resourceServiceUnavailable: '无法连接文件资源服务。',
      updateSucceeded: '版本信息已更新。',
      updateFailed: '版本信息更新失败。',
      deleteConfirmation: (version) => `确定删除版本 ${version} 和对应文件吗？此操作无法撤销。`,
      deleteSucceeded: (version) => `版本 ${version} 已删除。`,
      deleteFailed: '删除版本失败。',
    },
  },
  en: {
    languageLabel: 'Language',
    simulatingLabel: 'Simulating',
    simulatingOn: 'On',
    simulatingOff: 'Off',
    simulatingEnabled: 'Simulating enabled (SQLite)',
    simulatingDisabled: 'Simulating disabled (MongoDB)',
    simulatingUpdateFailed: 'Failed to update simulating mode',
    brandAria: 'Open Productions testing',
    navigationAria: 'Productions testing navigation',
    nav: {
      productLineTests: 'Product Line Tests',
      dataAutomationUpload: 'Automated Data Upload',
      deviceManagement: 'Device Management',
      testManagement: 'Test Management',
      dataManagement: 'Data Management',
      versionChecks: 'BOM Versions',
      sopDuroCheck: 'SOP & DURO Check',
      ecnCheck: 'ECN Check',
      engineeringChanges: 'Engineering Changes',
      ecn: 'ECN',
      contactLetters: 'Contact letters',
      productionAgent: 'Production Agent',
      downloads: 'Downloads',
    },
    status: {
      active: 'Active',
      ready: 'Ready',
      planned: 'Planned',
    },
    dashboard: {
      eyebrow: 'OPENTRONS FACTORY SYSTEMS',
      title: 'Productions testing',
      introduction: 'Factory data, robot operations, upload records, analysis workflows, and automation entry points.',
      openOperations: 'Automated Data Upload',
      viewModules: 'View Modules',
      modulesEyebrow: 'SYSTEM MAP',
      modulesTitle: 'Production Modules',
      operationsEyebrow: 'APPLICATION',
      operationsTitle: 'Production Operations',
      developerEyebrow: 'DEVELOPMENT',
      developerTitle: 'Developer Options',
      currentVersion: 'Current Version',
      lastUpdated: 'Last Updated',
      openModule: (name) => `Open ${name}`,
      comingSoon: 'Coming soon',
      modules: {
        operations: {
          name: 'Production Operations',
          summary: 'Production web app for uploads, robot operations, analysis, messages, and product tracking.',
        },
        versions: {
          name: 'Version Management',
          summary: 'Duro products, SOP analysis, BOM comparison, and scheduled version workflows.',
        },
        downloads: {
          name: 'Resource Downloads',
          summary: 'Versioned production files and downloadable resources managed by the unified API.',
        },
        agent: {
          name: 'Production Agent',
          summary: 'Agent workspace for production automation, assisted operations, and queue-based workflows.',
        },
      },
      routes: {
        devices: 'Devices',
        testCases: 'Test Cases',
        data: 'Data',
        uploadRecords: 'Upload Records',
        productManagement: 'Product Management',
        analysis: 'Analysis',
        messages: 'Messages',
        settings: 'Settings',
      },
    },
    downloads: {
      eyebrow: 'FILE RESOURCE LIBRARY',
      title: 'Downloads',
      introduction: 'Manage static file resources by project and version. Every upload is recorded in the database.',
      newUpload: 'Upload New Version',
      projectCount: (count) => `${count} resource project${count === 1 ? '' : 's'}`,
      refresh: 'Refresh',
      loading: 'Loading resource projects…',
      loadFailed: 'Unable to load file resources',
      retry: 'Retry',
      emptyTitle: 'No resource projects yet',
      emptyDescription: 'Select “Upload New Version” to create the first project and version.',
      createProject: 'Create Resource Project',
      versionCount: (count) => `${count} version${count === 1 ? '' : 's'}`,
      noProjectDescription: 'No project description',
      noVersions: 'This project does not have any versions yet.',
      noVersionNotes: 'No version notes',
      manageVersion: (version) => `Manage version ${version}`,
      downloadFile: 'Download File',
      editVersion: 'Edit Version Details',
      deleteVersion: 'Delete Version',
      newVersionEyebrow: 'NEW RESOURCE VERSION',
      editVersionEyebrow: 'EDIT VERSION',
      uploadTitle: 'Upload File Resource',
      editTitle: 'Edit Version Details',
      closeForm: 'Close form',
      projectName: 'Project Name',
      projectNamePlaceholder: 'Enter a new project name or select an existing project',
      projectNameHelp: 'Create a custom project or select an existing project and add a new version.',
      projectDescription: 'Project Description',
      projectDescriptionPlaceholder: 'Briefly describe the project and its resources',
      version: 'Version',
      versionPlaceholder: 'For example: 1.0.0',
      selectFile: 'Select File',
      versionNotes: 'Version Notes',
      versionNotesPlaceholder: 'Record changes, usage instructions, or notes for this version',
      removeSelectedFile: 'Remove selected file',
      uploading: (progress) => `Uploading ${progress}%`,
      saving: 'Saving…',
      cancel: 'Cancel',
      processing: 'Processing…',
      uploadAndCreate: 'Upload and Create Version',
      saveChanges: 'Save Changes',
      requestFailed: (status) => `Request failed (${status})`,
      unknownServerError: 'Unknown server error',
      versionRequired: 'Enter a version.',
      projectRequired: 'Enter or select a project name.',
      fileRequired: 'Select a file to upload.',
      uploadSucceeded: (version) => `Version ${version} was uploaded and saved.`,
      uploadFailed: 'File upload failed.',
      uploadRequestFailed: (status) => `Upload failed (${status})`,
      resourceServiceUnavailable: 'Unable to connect to the file resource service.',
      updateSucceeded: 'Version details were updated.',
      updateFailed: 'Unable to update version details.',
      deleteConfirmation: (version) => `Delete version ${version} and its file? This action cannot be undone.`,
      deleteSucceeded: (version) => `Version ${version} was deleted.`,
      deleteFailed: 'Unable to delete the version.',
    },
  },
}
