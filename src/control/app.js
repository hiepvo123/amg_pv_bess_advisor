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
import { SkyMesh } from 'three/addons/objects/SkyMesh.js';
import { pass, rangeFogFactor,color, fog, positionWorld, triNoise3D, normalWorld, uniform, densityFogFactor } from 'three/tsl';



export class App {
    scene;
    renderer;
    camera;
    controls;
    renderPipeline;

    //Lighting params
    timeOfDay;
    sun;
    ambient;

    //TODO: refactor this
    bladeInstancesMatrix;
    bladeInstances;

    solarPanelInstancesMatrix;
    solarPanelInstances;
    solarPanel;

    constructor(){
        this.scene = new THREE.Scene();

        this.renderer = new THREE.WebGPURenderer({antialias: true});

        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 100);
        this.camera.position.z = 5;
        this.camera.position.y = 5;
        this.timer = new THREE.Timer();
        this.timeOfDay = 0.25;
        
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

        await this.run();
    }

    async run() {
        //TODO: REFACTOR THIS MESS
        
        //assets
        this.controls = new OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.ambient = new THREE.AmbientLight(
            'white',
            1
        );
        this.scene.add( this.ambient );
        
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

        let solar_Panel = new SolarPanel(this.scene);
        solar_Panel.addToScene(this.scene);

        solar_Panel.setBases();

        
        

        const transmissionTower = new TransmissionTower(this.scene, 3);
        await transmissionTower.load();

        await transmissionTower.addToScene();
        let towerPos = new THREE.Vector3(-7,0,15);
        let towerPos2 = new THREE.Vector3(-7,0,-15);
        transmissionTower.setTowerPos(1,towerPos);
        transmissionTower.setTowerPos(2,towerPos2);
        

        
        const tree = new Tree(this.scene);
        await tree.load();

        tree.addToScene()

        
        const windTurbine = new WindTurbine(this.scene);

        await windTurbine.load();
        windTurbine.addToScene()
        



        //TODO: Day - Night cubemaps
        /*const loader = new THREE.CubeTextureLoader().setPath( './src/assets/cubemap/' );
        const cubeTexture = await loader.loadAsync( [
            'left.jpg', 'right.jpg', 'top.jpg', 'bottom.jpg', 'back.jpg', 'front.jpg'
        ] );
        this.scene.background = cubeTexture; */
        
        
        this.sun = new THREE.DirectionalLight( 0xffffff, 2 );
        this.sun.position.set(3, 20, 7.5);
        //DEFAULT TARGET IS (0,0,0);
        this.sun.castShadow = true;
        
        this.sun.shadow.mapSize.set( 4096, 4096 );
        this.sun.shadow.camera.left = -100;
        this.sun.shadow.camera.right = 100;
        this.sun.shadow.camera.top = 100;
        this.sun.shadow.camera.bottom = -100;
        this.sun.shadow.camera.near = 0.5;
        this.sun.shadow.camera.far = 100;
        const helper = new THREE.CameraHelper(this.sun.shadow.camera);
        this.scene.add(helper);
        
        
        this.scene.add( this.sun );
        

        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFShadowMap;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        
        const resize = () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        }
        window.addEventListener('resize', resize );



        const update_SolarPanels = () => {
            //this.solarPanelInstancesMatrix.rotation.y +=0.1
            if (this.sun.position.y > 0) {
                solar_Panel.lookAtPanels(this.sun.position);
            } else {
                solar_Panel.setPanelRotation(
                    new THREE.Euler(-Math.PI / 2, 0, 0)
                );
            }
        }
        //From https://threejsdemos.com/demos/lighting/day-cycle
        const update_light = () => {
            const t = this.timeOfDay
            const theta = t * Math.PI * 2
            const y = Math.sin(theta)
            const x = Math.cos(theta)
            this.sun.position.set(50 * x, 30 * Math.max(0.1, y), 2)
            const dayColor = new THREE.Color(0x87ceeb)
            const nightColor = new THREE.Color(0x0b1020)
            this.scene.background = dayColor.clone().lerp(nightColor, 1 - Math.max(0, y))
            const sunWarm = new THREE.Color(0xffe0a0)
            const moonBlue = new THREE.Color(0xaaccff)
            this.sun.color = sunWarm.clone().lerp(moonBlue, y < 0 ? 1 : 0)
            this.sun.intensity = y > 0 ? 2 * y : 0.2
            this.ambient.intensity = 0.1 + 0.4 * Math.max(0, y)
        }

        const animate = () => {
            this.timeOfDay = (this.timeOfDay + 0.00015) % 1
            update_light();

            //update_Blades();
            windTurbine.updateBlades();
            update_SolarPanels();



            this.controls.update();
            this.renderer.render(this.scene, this.camera);
        }
        this.renderer.setAnimationLoop(animate);

        

    

    }







    

}