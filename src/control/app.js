import * as THREE from 'three/webgpu'; 
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { Tree } from '../model/tree.js';
import { SolarPanel } from '../model/solar_panel.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { MTLLoader } from 'three/addons/loaders/MTLLoader.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import { CubeTextureLoader } from 'three';
import { VertexNormalsHelper } from 'three/addons/helpers/VertexNormalsHelper.js';
import { TransmissionTower } from '../model/transmission_tower.js';
import { WindTurbine } from '../model/wind_turbine.js';
import { PowerPredictions } from '../model/power_predictions.js';


export class App {
    scene;
    renderer;
    camera;
    controls;
    constructor(){
        this.scene = new THREE.Scene();

        this.renderer = new THREE.WebGPURenderer({antialias: true});

        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 35);
        this.camera.position.z = 5;

        
    }

    async init() {
        await this.renderer.init();

        this.renderer.setSize(
            window.innerWidth,
            window.innerHeight
        );

        document.body.appendChild(
            this.renderer.domElement
        );

        await this.createAssets();
    }

    async createAssets() {
        //assets
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        const light = new THREE.AmbientLight(
            0xffffff,
            1
        );
        this.scene.add( light );
        
        const cubeGeometry = new THREE.BoxGeometry(1, 1, 1);
        const cubeMaterial = new THREE.MeshPhongMaterial({ color: 0x00ff00 });
        
        
        const geometry = new THREE.PlaneGeometry( 1, 1 );
        const material = new THREE.MeshPhongMaterial( {color: 0x999999, side: THREE.DoubleSide} );
        var texture = new THREE.TextureLoader().load('./src/assets/grass.jpg');
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        texture.repeat.set( 10, 10 );
        material.map = texture;
        const plane = new THREE.Mesh( geometry, material );
        
        plane.rotateX(Math.PI / 2);
        plane.scale.set(100, 100, 1);
        plane.receiveShadow = true;
        this.scene.add( plane );
        
        const transmissionTower = new TransmissionTower();
        this.scene.add(transmissionTower.getObject());
        
        const tree = new Tree();
        await tree.load();
        this.scene.add(tree.getObject())
        
        const windTurbine = new WindTurbine();
        
        
        this.scene.add(windTurbine.mesh);
        await windTurbine.load();
        
        const loader = new THREE.CubeTextureLoader().setPath( './src/assets/cubemap/' );
        const cubeTexture = await loader.loadAsync( [
            'left.jpg', 'right.jpg', 'top.jpg', 'bottom.jpg', 'back.jpg', 'front.jpg'
        ] );
        this.scene.background = cubeTexture;
        
        
        const directionalLight = new THREE.DirectionalLight( 0xffffff, 2 );
        directionalLight.position.set(5, 10, 7.5);
        directionalLight.castShadow = true;
        
        directionalLight.shadow.mapSize.width = 1024;
        directionalLight.shadow.mapSize.height = 1024;
        directionalLight.shadow.camera.near = 0.5;
        directionalLight.shadow.camera.far = 50;
        
        
        this.scene.add( directionalLight );
        console.log(this.scene.children);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFShadowMap;
    }

    update() {
        this.renderer.setAnimationLoop(this.renderloop);
        //resize
        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });
    }

    renderloop = () => {

        //if (windTurbine.blades) {
        //    windTurbine.blades.rotation.y += 0.01;
        //}
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
        //window.requestAnimationFrame(renderloop);
        
        
    }
}