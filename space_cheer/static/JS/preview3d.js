(function(global) {
  'use strict';

  // Configuración por defecto
  var DEFAULT_OPTIONS = {
    modelUrl: null,
    defaultColor: '#2563eb',
    accentColor: '#ffffff',
    autoRotate: true,
    autoRotateSpeed: 0.003,
    enableControls: false,
    enableZoom: true,
    enablePan: true,
    transparentBackground: true,
    shadowQuality: 'medium',
    onModelLoad: null,
    onError: null,
    onReady: null,
  };

  // Estado interno
  var state = {
    container: null,
    renderer: null,
    scene: null,
    camera: null,
    mesh: null,
    modelRoot: null,
    clock: null,
    animationId: null,
    options: {},
    isInitialized: false,
    isDestroyed: false,
    resizeHandler: null,
    controls: null,
  };

  // Utilidades
  function mergeOptions(userOptions) {
    var opts = {};
    for (var k in DEFAULT_OPTIONS) {
      opts[k] = (userOptions && userOptions[k] !== undefined) ? userOptions[k] : DEFAULT_OPTIONS[k];
    }
    return opts;
  }

  function log() {
    if (console && console.log) console.log('[Preview3D]', Array.prototype.slice.call(arguments).join(' '));
  }
  function warn() { if (console && console.warn) console.warn('[Preview3D]', Array.prototype.slice.call(arguments).join(' ')); }
  function error() { if (console && console.error) console.error('[Preview3D]', Array.prototype.slice.call(arguments).join(' ')); }

  // Uniforme de porrista estilizado low-poly, construido con primitivas.
  // Tintable via setColor(). Se usa cuando el producto no tiene GLB propio.
  function createTintableMaterial(color) {
    return new THREE.MeshStandardMaterial({
      color: color || state.options.defaultColor,
      roughness: 0.7,
      metalness: 0.1,
      side: THREE.DoubleSide,
    });
  }

  function createAccentMaterial() {
    return new THREE.MeshStandardMaterial({
      color: state.options.accentColor,
      roughness: 0.8,
      metalness: 0.0,
      side: THREE.DoubleSide,
    });
  }

  function createGenericUniform(color) {
    var group = new THREE.Group();
    var main = createTintableMaterial(color);
    var accent = createAccentMaterial();

    // Torso / top (caja achatada)
    var top = new THREE.Mesh(new THREE.BoxGeometry(0.72, 0.55, 0.3), main);
    top.position.y = 0.55;
    group.add(top);

    // Franja del top (accent, no se tiñe)
    var stripe = new THREE.Mesh(new THREE.BoxGeometry(0.74, 0.12, 0.32), accent);
    stripe.position.y = 0.72;
    group.add(stripe);

    // Hombros (esferas achatadas)
    var shoulderGeo = new THREE.SphereGeometry(0.14, 12, 8);
    var shoulderL = new THREE.Mesh(shoulderGeo, main);
    shoulderL.position.set(-0.42, 0.76, 0);
    shoulderL.scale.y = 0.7;
    group.add(shoulderL);
    var shoulderR = shoulderL.clone();
    shoulderR.position.x = 0.42;
    group.add(shoulderR);

    // Falda (cono truncado abierto)
    var skirt = new THREE.Mesh(
      new THREE.CylinderGeometry(0.38, 0.62, 0.45, 16, 1, true),
      main
    );
    skirt.position.y = 0.02;
    group.add(skirt);

    // Ribete de la falda (accent)
    var hem = new THREE.Mesh(
      new THREE.CylinderGeometry(0.62, 0.64, 0.06, 16, 1, true),
      accent
    );
    hem.position.y = -0.2;
    group.add(hem);

    group.traverse(function (child) {
      if (child.isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
        // Marca para que setColor() sepa qué mallas teñir
        child.userData.tintable = child.material === main;
      }
    });
    return group;
  }

  // Luces
  function setupLights() {
    var ambient = new THREE.AmbientLight(0xffffff, 0.6);
    state.scene.add(ambient);

    var dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
    dirLight.position.set(3, 5, 4);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.width = 1024;
    dirLight.shadow.mapSize.height = 1024;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 20;
    dirLight.shadow.camera.left = -5;
    dirLight.shadow.camera.right = 5;
    dirLight.shadow.camera.top = 5;
    dirLight.shadow.camera.bottom = -5;
    dirLight.shadow.bias = -0.001;
    state.scene.add(dirLight);

    var fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-3, 2, -3);
    state.scene.add(fillLight);

    var hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.4);
    state.scene.add(hemiLight);
  }

  // Init Three.js
  function initThreeJS() {
    var container = state.container;
    var width = container.clientWidth;
    var height = container.clientHeight;

    state.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: state.options.transparentBackground,
      powerPreference: 'high-performance',
    });
    state.renderer.setSize(width, height);
    state.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    state.renderer.shadowMap.enabled = true;
    state.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    state.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    state.renderer.toneMappingExposure = 1.0;
    state.renderer.outputEncoding = THREE.sRGBEncoding;

    container.innerHTML = '';
    container.appendChild(state.renderer.domElement);

    state.scene = new THREE.Scene();
    if (!state.options.transparentBackground) {
      state.scene.background = new THREE.Color(0xf5f5f5);
    }

    var aspect = width / height;
    state.camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100);
    state.camera.position.set(0, 0.75, 3);
    state.camera.lookAt(0, 0, 0);

    setupLights();

    if (state.options.enableControls && THREE.OrbitControls) {
      state.controls = new THREE.OrbitControls(state.camera, state.renderer.domElement);
      state.controls.enableDamping = true;
      state.controls.dampingFactor = 0.08;
      state.controls.enableZoom = state.options.enableZoom;
      state.controls.enablePan = state.options.enablePan;
      state.controls.minDistance = 1.2;
      state.controls.maxDistance = 8;
      state.controls.target.set(0, 0.2, 0);
      // La primera interacción pausa la rotación automática
      state.controls.addEventListener('start', function () {
        state.options.autoRotate = false;
      });
    }

    state.mesh = createGenericUniform(state.options.defaultColor);
    state.mesh.position.y = -0.3;
    state.scene.add(state.mesh);

    var groundGeo = new THREE.PlaneGeometry(10, 10);
    var groundMat = new THREE.ShadowMaterial({ opacity: 0.15 });
    var ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.75;
    ground.receiveShadow = true;
    state.scene.add(ground);

    state.clock = new THREE.Clock();
    log('Three.js inicializado:', width + 'x' + height);
  }

  // Animation loop
  function animate() {
    if (state.isDestroyed) return;
    state.animationId = requestAnimationFrame(animate);
    var delta = state.clock.getDelta();

    if (state.options.autoRotate) {
      var target = state.modelRoot || state.mesh;
      if (target) target.rotation.y += state.options.autoRotateSpeed;
    }

    if (state.modelRoot && state.mixer) {
      state.mixer.update(delta);
    }

    if (state.controls) state.controls.update();

    if (state.renderer && state.scene && state.camera) {
      state.renderer.render(state.scene, state.camera);
    }
  }

  // Resize
  function onResize() {
    if (state.isDestroyed || !state.renderer || !state.camera || !state.container) return;
    var width = state.container.clientWidth;
    var height = state.container.clientHeight;
    if (width === 0 || height === 0) return;
    state.camera.aspect = width / height;
    state.camera.updateProjectionMatrix();
    state.renderer.setSize(width, height);
  }

  // Load GLTF model
  function loadModel(url, options) {
    options = options || {};
    if (!url) { warn('loadModel sin URL'); return Promise.resolve(null); }
    if (!THREE.GLTFLoader) {
      var err = new Error('GLTFLoader no disponible');
      error(err);
      if (state.options.onError) state.options.onError(err);
      return Promise.reject(err);
    }
    log('Cargando modelo GLTF:', url);
    var loader = new THREE.GLTFLoader();
    return new Promise(function(resolve, reject) {
      loader.load(url, function(gltf) {
        log('Modelo GLTF cargado');
        if (state.mesh && state.mesh.parent) {
          state.scene.remove(state.mesh);
          state.mesh.traverse(function (child) {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
              if (Array.isArray(child.material)) child.material.forEach(function (m) { m.dispose(); });
              else child.material.dispose();
            }
          });
          state.mesh = null;
        }
        state.modelRoot = gltf.scene;
        state.modelRoot.traverse(function(child) {
          if (child.isMesh) { child.castShadow = true; child.receiveShadow = true; }
        });
        var box = new THREE.Box3().setFromObject(state.modelRoot);
        var center = box.getCenter(new THREE.Vector3());
        var size = box.getSize(new THREE.Vector3());
        var maxDim = Math.max(size.x, size.y, size.z);
        var scale = 1.5 / maxDim;
        state.modelRoot.scale.multiplyScalar(scale);
        state.modelRoot.position.sub(center.clone().multiplyScalar(scale));
        state.modelRoot.position.y += 0.75;
        state.scene.add(state.modelRoot);
        if (gltf.animations && gltf.animations.length > 0) {
          state.mixer = new THREE.AnimationMixer(state.modelRoot);
          gltf.animations.forEach(function(clip) { state.mixer.clipAction(clip).play(); });
        }
        if (state.options.onModelLoad) state.options.onModelLoad(gltf);
        if (options.onLoad) options.onLoad(gltf);
        resolve(gltf);
      }, function(xhr) { if (options.onProgress) options.onProgress(xhr); }, function(err) {
        error('Error cargando GLTF:', err);
        if (state.options.onError) state.options.onError(err);
        if (options.onError) options.onError(err);
        reject(err);
      });
    });
  }

  // API Pública
  var Preview3D = {
    init: function(containerSelector, options) {
      if (state.isInitialized) { warn('Ya inicializado'); this.destroy(); }
      var container = typeof containerSelector === 'string' ? document.querySelector(containerSelector) : containerSelector;
      if (!container) { var err = new Error('Contenedor no encontrado: ' + containerSelector); error(err); throw err; }
      state.container = container;
      state.options = mergeOptions(options);
      state.isInitialized = true;
      state.isDestroyed = false;
      log('Inicializando Preview3D en', containerSelector);
      if (typeof THREE === 'undefined' || !THREE.WebGLRenderer) {
        var err = new Error('Three.js no cargado'); error(err); throw err;
      }
      try { var canvas = document.createElement('canvas'); var gl = canvas.getContext('webgl2') || canvas.getContext('webgl'); if (!gl) throw new Error('WebGL no soportado'); } catch(e) { error('WebGL no disponible:', e); if (state.options.onError) state.options.onError(e); }
      initThreeJS();
      if (state.options.modelUrl) { loadModel(state.options.modelUrl).catch(function(err){ warn('Fallo modelo, usando placeholder:', err.message); }); }
      state.resizeHandler = onResize.bind(null);
      window.addEventListener('resize', state.resizeHandler);
      animate();
      if (state.options.onReady) setTimeout(state.options.onReady, 0);
      log('Preview3D listo');
      return this;
    },
    destroy: function() {
      if (!state.isInitialized || state.isDestroyed) return;
      log('Destruyendo Preview3D');
      state.isDestroyed = true;
      if (state.animationId) { cancelAnimationFrame(state.animationId); state.animationId = null; }
      if (state.resizeHandler) { window.removeEventListener('resize', state.resizeHandler); state.resizeHandler = null; }
      if (state.controls) { state.controls.dispose(); state.controls = null; }
      if (state.renderer) { state.renderer.dispose(); state.renderer.forceContextLoss(); state.renderer.domElement.remove(); state.renderer = null; }
      if (state.scene) { state.scene.traverse(function(obj){ if(obj.geometry) obj.geometry.dispose(); if(obj.material){ if(Array.isArray(obj.material)) obj.material.forEach(function(m){m.dispose();}); else obj.material.dispose(); } }); state.scene = null; }
      state.camera = null; state.mesh = null; state.modelRoot = null; state.mixer = null; state.clock = null; state.container = null; state.options = {}; state.isInitialized = false; state.controls = null;
      log('Preview3D destruido');
    },
    loadModel: function(url, options) { return loadModel(url, options); },
    setColor: function (hexColor) {
      // Solo tiñe el uniforme genérico. Los GLB reales conservan sus texturas.
      if (state.modelRoot) return;
      if (!state.mesh) return;
      state.mesh.traverse(function (child) {
        if (child.isMesh && child.userData.tintable && child.material.color) {
          child.material.color.set(hexColor);
        }
      });
    },
    resize: function() { onResize(); },
    getState: function() { return { isInitialized: state.isInitialized, isDestroyed: state.isDestroyed, hasModel: !!state.modelRoot, container: state.container }; },
  };

  global.Preview3D = Preview3D;
  if (typeof module !== 'undefined' && module.exports) module.exports = Preview3D;
  if (typeof define === 'function' && define.amd) define([], function(){ return Preview3D; });
})(typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : this);