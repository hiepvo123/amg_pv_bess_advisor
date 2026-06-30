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

        await this.createAssets();
    }

    async createAssets() {
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

        this.solarPanel = new SolarPanel(this.scene);
        this.solarPanelInstances = [];
        const solarPanelCount = 36;
        const solarBaseInstance = []
        this.solarPanel.addToScene();

        

        let solar_Panel = new SolarPanel(this.scene);

        
        

        const transmissionTower = new TransmissionTower(this.scene, 3);
        await transmissionTower.load();

        await transmissionTower.addToScene();
        let towerPos = new THREE.Vector3(-7,0,0);
        transmissionTower.setTowerPos(0,towerPos);
        

        
        const tree = new Tree();
        await tree.load();

        const instancedMeshes = [];
        const treeCount = 400;

        tree.meshes.forEach((mesh) => {
            const im = new THREE.InstancedMesh(
                mesh.geometry,
                mesh.material,
                treeCount
            );

            im.castShadow = true;
            im.receiveShadow = true;

            this.scene.add(im);
            instancedMeshes.push(im);
        });

        const treeMatrix = new THREE.Object3D();
        treeMatrix.scale.set(0.5,0.5,0.5);

        const clearRadius = 15; // empty square from -10 to 10

        for (let i = 0; i < treeCount; i++) {
            let x, z;

            do {
                x = Math.random() * 100 - 50;
                z = Math.random() * 100 - 50;
            } while (
                Math.abs(x) < clearRadius &&
                Math.abs(z) < clearRadius
            );

            treeMatrix.position.set(x, 0, z);
            //treeMatrix.scale.set(0.75,0.75,0.75);
            
            //treeMatrix.rotation.y = Math.random() * Math.PI * 2;

            treeMatrix.updateMatrix();

            instancedMeshes.forEach((im) => {
                im.setMatrixAt(i, treeMatrix.matrix);
                im.instanceMatrix.needsUpdate = true;
            });
        }

        
        const windTurbine = new WindTurbine();

        await windTurbine.load();
        const instancedTurbines = [];
        this.bladeInstances =[];

        windTurbine.meshes.forEach((mesh) => {
            //console.log(
            //    mesh.name,
            //    mesh.position,
            //    mesh.rotation
            //);

            const im = new THREE.InstancedMesh(
                mesh.geometry,
                mesh.material,
                10
            );

            im.castShadow = true;
            //im.receiveShadow = true;

            if (mesh.name === 'WindTurbine_Blades001_Material002_0') {
                this.bladeInstances.push(im) ;
            } else {
                instancedTurbines.push(im);
            }

            this.scene.add(im);

        });

        const bodyTurbineMatrix = new THREE.Object3D();
        this.bladeInstancesMatrix = new THREE.Object3D();
        bodyTurbineMatrix.scale.set(2,2,2);
        this.bladeInstancesMatrix.scale.set(2,2,2);

        for (let i = 0; i < 5; i++) {
            bodyTurbineMatrix.position.set(5, 8.2, 5 + 3*i);
            bodyTurbineMatrix.rotation.x = -Math.PI / 2;
            bodyTurbineMatrix.updateMatrix();

            instancedTurbines.forEach((im) => {
                im.setMatrixAt(i, bodyTurbineMatrix.matrix);
                im.instanceMatrix.needsUpdate = true
            });

            //bladeInstances.setMatrixAt(i, bladeDummy.matrix);
        }

        for (let i = 5; i < 10; i++) {
            bodyTurbineMatrix.position.set(8, 8.2, 5 + 3*(9-i));
            bodyTurbineMatrix.rotation.x = -Math.PI / 2;
            bodyTurbineMatrix.updateMatrix();

            instancedTurbines.forEach((im) => {
                im.setMatrixAt(i, bodyTurbineMatrix.matrix);
                im.instanceMatrix.needsUpdate = true
            });

            //bladeInstances.setMatrixAt(i, bladeDummy.matrix);
        }



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
        
        this.sun.shadow.mapSize.width = 2048;
        this.sun.shadow.mapSize.height = 2048;
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


    update_Blades() {
        this.bladeInstancesMatrix.rotation.y +=0.01;
        console.log(this.bladeInstances.length);

        for(let i = 0; i < 5; i++){

            this.bladeInstancesMatrix.position.set(5 , 8.2, 5 + 3*i);
            this.bladeInstancesMatrix.rotation.x = -Math.PI / 2;
            this.bladeInstancesMatrix.updateMatrix();
            this.bladeInstances.forEach((im) => {
                im.setMatrixAt(i, this.bladeInstancesMatrix.matrix);
                im.instanceMatrix.needsUpdate = true;
            });
        }

        
        for(let i = 5; i < 10; i++){

            this.bladeInstancesMatrix.position.set(8 , 8.2, 5 + 3*(9-i));
            this.bladeInstancesMatrix.rotation.x = -Math.PI / 2;
            this.bladeInstancesMatrix.updateMatrix();
            this.bladeInstances.forEach((im) => {
                im.setMatrixAt(i, this.bladeInstancesMatrix.matrix);
                im.instanceMatrix.needsUpdate = true;
            });
        }
    }

    update_SolarPanels(){
        //this.solarPanelInstancesMatrix.rotation.y +=0.1

        let index = 0;
        for (let x = 5; x <= 10; x++) {
            for (let z = 0; z <= 5; z++) {


                this.solarPanel.solarPanelInstancesMatrix.position.set(x*2.5 -15, 1, -z*3);

                if (this.sun.position.y > 0) {
                    this.solarPanel.solarPanelInstancesMatrix.lookAt(this.sun.position);
                } else {
                        // Slowly return to looking up
                    this.solarPanel.solarPanelInstancesMatrix.rotation.x =
                        THREE.MathUtils.lerp(
                            this.solarPanel.solarPanelInstancesMatrix.rotation.x,
                            -Math.PI / 2,
                            0.02
                        );

                    this.solarPanel.solarPanelInstancesMatrix.rotation.y =
                        THREE.MathUtils.lerp(
                            this.solarPanel.solarPanelInstancesMatrix.rotation.y,
                            0,
                            0.02
                        );

                    this.solarPanel.solarPanelInstancesMatrix.rotation.z =
                        THREE.MathUtils.lerp(
                            this.solarPanel.solarPanelInstancesMatrix.rotation.z,
                            0,
                            0.02
                        );
                
                    }
                this.solarPanel.solarPanelInstancesMatrix.updateMatrix();

                this.solarPanel.solarPanelInstances.forEach((im) => {
                    const finalMatrix = this.solarPanel.solarPanelInstancesMatrix.matrix.clone();
                    finalMatrix.multiply(im.userData.localMatrix);

                    im.setMatrixAt(index, finalMatrix);
                    im.instanceMatrix.needsUpdate = true;

                });

                index++;
            }
        }

    }

    //From https://threejsdemos.com/demos/lighting/day-cycle
    update_light(time) {
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

    renderloop = () => {
        this.timeOfDay = (this.timeOfDay + 0.00015) % 1
        this.update_light();

        this.update_Blades();
        this.update_SolarPanels();



        this.controls.update();
        this.renderer.render(this.scene, this.camera);
        //window.requestAnimationFrame(renderloop);
        
        
    }
}