// glb 资产加载 + 进度事件
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

export function loadGLB(url, manager) {
  const loader = new GLTFLoader(manager);
  return loader.loadAsync(url).then((gltf) => gltf.scene);
}

export function createLoadingManager({ onProgress, onLoad }) {
  const manager = new THREE.LoadingManager();
  manager.onProgress = (_url, loaded, total) =>
    onProgress && onProgress(loaded / Math.max(total, 1));
  manager.onLoad = () => onLoad && onLoad();
  return manager;
}
