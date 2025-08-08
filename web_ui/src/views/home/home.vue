<template>
  <div class="dashboard-container">
    <!-- 浮动背景元素 -->
    <div class="floating-elements">
      <div class="floating-circle circle-1"></div>
      <div class="floating-circle circle-2"></div>
      <div class="floating-circle circle-3"></div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 顶部标题和版本信息 -->
       <p class="version-info">当前版本: v2.5.1 | 最后更新: 2023-11-15</p>

      <!-- 通知轮播 -->
      <div class="notification-ticker">
        <div class="ticker-header">
          <span class="ticker-icon">🔔</span>
          <span>平台公告</span>
        </div>
        <marquee class="ticker-content" behavior="scroll" direction="left">
          系统维护通知: 本周六凌晨2:00-4:00进行系统升级 | 新功能上线: 96通道移液器测试模块已发布 | 温馨提示: 请及时备份您的测试数据
        </marquee>
      </div>

     
      <!-- 最新动态 -->
      <div class="news-section">
        <h2 class="section-title">最新动态</h2>
        <div class="news-cards">
          <div 
            v-for="(news, index) in newsList" 
            :key="index"
            class="news-card"
          >
            <div class="news-date">{{ news.date }}</div>
            <h3 class="news-title">{{ news.title }}</h3>
            <p class="news-content">{{ news.content }}</p>
            <div class="news-tag" :class="'tag-' + news.type">{{ news.type }}</div>
          </div>
        </div>
      </div>

      <!-- 历史动态 -->
      <div class="history-section">
        <h2 class="section-title">
          历史动态
          <span class="toggle-history" @click="toggleHistory">
            {{ showAllHistory ? '收起全部' : '展开全部' }}
          </span>
        </h2>
        
        <div class="history-list">
          <div 
            v-for="(item, index) in visibleHistory" 
            :key="index"
            class="history-item"
            :class="{ 'expanded': item.expanded }"
          >
            <div class="history-header" @click="toggleItem(index)">
              <div class="history-date">{{ item.date }}</div>
              <div class="history-title">{{ item.title }}</div>
              <div class="history-arrow">
                {{ item.expanded ? '▼' : '▶' }}
              </div>
            </div>
            
            <div class="history-content" v-if="item.expanded">
              <p>{{ item.content }}</p>
              <div class="history-images" v-if="item.images">
                <img 
                  v-for="(img, imgIndex) in item.images" 
                  :key="imgIndex"
                  :src="img" 
                  alt="历史图片"
                >
              </div>
            </div>
          </div>
        </div>

         <!-- 快捷操作区 -->
      <div class="quick-actions-section">
        <h2 class="section-title">快捷操作</h2>
        <div class="action-buttons">
          <button 
            v-for="action in quickActions" 
            :key="action.text"
            class="action-button"
            @click="handleQuickAction(action)"
          >
            <span class="button-icon">{{ action.icon }}</span>
            {{ action.text }}
          </button>
        </div>
      </div>

      <!-- 快捷链接区 -->
      <div class="quick-links-section">
        <h2 class="section-title">常用链接</h2>
        <div class="link-buttons">
          <a
            v-for="link in quickLinks"
            :key="link.text"
            :href="link.url"
            class="link-button"
            target="_blank"
          >
            <span class="button-icon">{{ link.icon }}</span>
            {{ link.text }}
          </a>
        </div>
      </div>


      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from 'vue';

// 版本信息
const versionInfo = {
  current: 'v2.5.1',
  lastUpdated: '2023-11-15'
};

// 快捷操作
const quickActions = ref([
  { icon: '⚙️', text: '设备控制', action: 'deviceControl' },
  { icon: '📊', text: '数据分析', action: 'dataAnalysis' },
  { icon: '📁', text: '文件管理', action: 'fileManagement' },
  { icon: '📝', text: '新建测试', action: 'createTest' },
  { icon: '👥', text: '用户管理', action: 'userManagement' },
  { icon: '🔧', text: '系统设置', action: 'systemSettings' }
]);

// 快捷链接
const quickLinks = ref([
  { icon: '', text: '谷歌Drive', url: 'https://drive.google.com/drive/' },
  { icon: '', text: '谷歌邮箱', url: 'https://mail.google.com/' },
  { icon: '', text: '谷歌日历', url: 'https://calendar.google.com/calendar/u/0/r?pli=1'},
  { icon: '', text: '测试总表', url: 'https://knowledgebase.opentrons.com' }
]);

// 最新动态
const newsList = ref([
  {
    date: '2023-11-10',
    title: 'OT3测试模块重大更新',
    content: '新增了温度控制测试项，优化了运动控制测试流程',
    type: '更新'
  },
  {
    date: '2023-11-05',
    title: '平台使用培训通知',
    content: '本周五下午3点将举行新功能使用培训，请相关人员准时参加',
    type: '通知'
  },
  {
    date: '2023-10-28',
    title: '数据导出功能优化',
    content: '测试数据导出现在支持CSV和Excel两种格式',
    type: '优化'
  }
]);

// 历史动态
const historyData = ref([
  {
    date: '2023-11-20',
    title: '系统升级完成通知',
    content: '本次系统升级已完成，新增了设备远程控制功能，优化了测试数据统计页面。升级内容包括：1. 新增OT3设备控制模块；2. 优化数据导出格式；3. 修复了已知的3个问题。',
    images: [],
    expanded: false
  },
  {
    date: '2023-11-15',
    title: '新测试标准发布',
    content: '发布新的移液器测试标准V2.3，主要变更包括：1. 精度测试标准提高至±0.5%；2. 新增温度稳定性测试项；3. 延长耐久性测试周期至10000次。',
    expanded: false
  },
  {
    date: '2023-11-10',
    title: '实验室安全培训',
    content: '本周五下午2点将举行实验室安全培训，内容包括：1. 设备操作规范；2. 紧急情况处理；3. 新安全系统使用。请全体测试人员准时参加。',
    expanded: false
  },
  {
    date: '2023-11-05',
    title: '测试数据备份提醒',
    content: '系统将于本周六凌晨进行维护，请各部门在周五下班前完成重要测试数据的备份工作。备份路径：文件管理->数据导出->选择CSV或Excel格式。',
    expanded: false
  },
  {
    date: '2023-10-30',
    title: '新设备投入使用',
    content: '新型OT3设备已完成验收测试，现已正式投入使用。设备编号：OT3-2023-001至OT3-2023-005，请测试人员按照新操作手册进行测试。',
    images: [],
    expanded: false
  }
]);

const showAllHistory = ref(false);
const displayCount = ref(3); // 默认显示3条

// 计算显示的动态
const visibleHistory = computed(() => {
  return showAllHistory.value 
    ? historyData.value 
    : historyData.value.slice(0, displayCount.value);
});

// 切换显示全部/部分
const toggleHistory = () => {
  showAllHistory.value = !showAllHistory.value;
  
  // 同步所有项目的展开状态
  historyData.value.forEach(item => {
    item.expanded = showAllHistory.value;
  });
};

// 切换单条展开状态
const toggleItem = (index: number) => {
  historyData.value[index].expanded = !historyData.value[index].expanded;
};

// 处理快捷操作
const handleQuickAction = (action: any) => {
  console.log('执行操作:', action.text);
  // 这里可以替换为实际的操作逻辑
  // 例如: router.push(`/${action.action}`)
};
</script>

<style lang="scss" scoped>
.dashboard-container {
  position: relative;
  min-height: 100vh;
  padding: 2rem;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
  overflow: hidden;
}

.floating-elements {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  z-index: 0;
}

.floating-circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(0, 120, 212, 0.1);
  filter: blur(60px);
}

.circle-1 {
  width: 300px;
  height: 300px;
  top: -50px;
  left: -50px;
  animation: float 15s infinite ease-in-out;
}

.circle-2 {
  width: 400px;
  height: 400px;
  bottom: -100px;
  right: -100px;
  animation: float 18s infinite ease-in-out reverse;
}

.circle-3 {
  width: 200px;
  height: 200px;
  top: 50%;
  right: 10%;
  animation: float 12s infinite ease-in-out;
}

@keyframes float {
  0%, 100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(20px, 20px);
  }
}

.main-content {
  position: relative;
  z-index: 1;
  max-width: 1200px;
  margin: 0 auto;
}

.header-section {
  text-align: center;
  margin-bottom: 2rem;
}

.main-title {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
  color: #333;
  
  .highlight {
    color: #0078d4;
    font-weight: 600;
  }
}

.version-info {
  color: #666;
  font-size: 0.9rem;
}

.notification-ticker {
  background: #fff;
  border-radius: 8px;
  padding: 0.8rem 1.2rem;
  margin: 2rem 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-left: 4px solid #0078d4;
  
  .ticker-header {
    display: flex;
    align-items: center;
    margin-bottom: 0.5rem;
    font-weight: 600;
    color: #0078d4;
    
    .ticker-icon {
      margin-right: 8px;
    }
  }
  
  .ticker-content {
    color: #555;
    white-space: nowrap;
  }
}

.section-title {
  font-size: 1.5rem;
  margin: 2rem 0 1rem;
  color: #444;
  position: relative;
  padding-left: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: 4px;
    background: #0078d4;
    border-radius: 2px;
  }
  
  .toggle-history {
    font-size: 0.9rem;
    color: #0078d4;
    cursor: pointer;
    &:hover {
      text-decoration: underline;
    }
  }
}

.quick-actions-section,
.quick-links-section {
  margin-bottom: 1rem;
}

.action-buttons,
.link-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.action-button,
.link-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 1rem;
  text-decoration: none;
  color: inherit;
  
  &:hover {
    background: #0078d4;
    color: white;
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
    
    .button-icon {
      transform: scale(1.1);
    }
  }
  
  .button-icon {
    margin-right: 0.5rem;
    transition: transform 0.3s ease;
  }
}

.link-button {
  background: #f0f7ff;
  color: #0078d4;
  
  &:hover {
    background: #0078d4;
    color: white;
  }
}

.news-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  margin-top: 1rem;
}

.news-card {
  background: #fff;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  position: relative;
  overflow: hidden;
  
  &:hover {
    transform: translateY(-5px);
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
  }
  
  .news-date {
    font-size: 0.8rem;
    color: #888;
    margin-bottom: 0.5rem;
  }
  
  .news-title {
    font-size: 1.1rem;
    margin-bottom: 0.8rem;
    color: #333;
  }
  
  .news-content {
    font-size: 0.9rem;
    color: #666;
    line-height: 1.5;
  }
  
  .news-tag {
    position: absolute;
    top: 0;
    right: 0;
    padding: 0.3rem 0.8rem;
    font-size: 0.7rem;
    border-bottom-left-radius: 8px;
    color: white;
    
    &.tag-更新 {
      background: #0078d4;
    }
    
    &.tag-通知 {
      background: #ffaa44;
    }
    
    &.tag-优化 {
      background: #22bb66;
    }
  }
}

.history-section {
  margin-top: 2rem;
  background: #fff;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.history-item {
  border: 1px solid #eee;
  border-radius: 6px;
  overflow: hidden;
  transition: all 0.3s ease;
  
  &:hover {
    border-color: #ddd;
  }
  
  &.expanded {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

.history-header {
  display: flex;
  align-items: center;
  padding: 0.8rem 1rem;
  background: #f9f9f9;
  cursor: pointer;
  user-select: none;
  
  .history-date {
    width: 100px;
    color: #666;
    font-size: 0.85rem;
  }
  
  .history-title {
    flex: 1;
    font-weight: 500;
  }
  
  .history-arrow {
    width: 20px;
    text-align: center;
    color: #999;
  }
}

.history-content {
  padding: 1rem;
  background: #fff;
  border-top: 1px solid #eee;
  
  p {
    margin: 0 0 1rem 0;
    line-height: 1.6;
    color: #555;
  }
}

.history-images {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
  
  img {
    width: 120px;
    height: 90px;
    object-fit: cover;
    border-radius: 4px;
    cursor: pointer;
    transition: transform 0.2s;
    
    &:hover {
      transform: scale(1.03);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .action-buttons,
  .link-buttons {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }
  
  .news-cards {
    grid-template-columns: 1fr;
  }
  
  .history-header {
    flex-wrap: wrap;
    
    .history-date {
      width: 100%;
      margin-bottom: 0.3rem;
    }
  }
  
  .history-images {
    flex-wrap: wrap;
    
    img {
      width: 100%;
      height: auto;
    }
  }
}
</style>