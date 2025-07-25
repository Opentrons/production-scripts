import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
// import legacy from '@vitejs/plugin-legacy';
// import AutoImport from 'unplugin-auto-import/vite';
// import Components from 'unplugin-vue-components/vite';
// import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
// import { viteSingleFile } from 'vite-plugin-singlefile';
// // https://vitejs.dev/config/
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 8000,
    open: true
  },
  build: {
    outDir: '../dist/' // 指定编译后文件的输出目录
  },
  base: './',
  plugins: [
    // legacy({
    //   targets:['defaults','not IE 11'],
    //   polyfills: ['es.promise.finally']
    //   }),
    vue(),
   
  ],
 
});
