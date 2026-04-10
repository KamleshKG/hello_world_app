pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'
        WORKSPACE = '/var/lib/jenkins/.jenkins/workspace/flutter-hello-world_main'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io'
        ARTIFACTORY_REPO = 'flutter-app-releases-generic-local'
        ARTIFACTORY_CREDS = credentials('artifactory-token')
    }
    stages {
        stage('Fix Permissions') {
            steps {
                sh '''
                # Temporary permission fix (test env only)
                sudo chmod 777 ${WORKSPACE}
                '''
            }
        }

        stage('Regenerate Android') {
            steps {
                sh '''
                cd ${WORKSPACE}
                mkdir -p backup
                [ -d "android" ] && mv android backup/android_$(date +%s)
                flutter create --platforms android .
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                cd ${WORKSPACE}
                echo "sdk.dir=${ANDROID_SDK_ROOT}" > android/local.properties
                flutter clean
                flutter pub get
                flutter build apk --release
                '''
            }
        }

        stage('Reset Permissions') {
            steps {
                sh '''
                sudo chmod 755 ${WORKSPACE}
                sudo chown -R jenkins:jenkins ${WORKSPACE}
                '''
            }
        }
        
        stage('Publish to Artifactory') {
            steps {
                script {
                    // Alternative 1: Use exact path (recommended for simplicity)
                    def apkPath = "${WORKSPACE}/build/app/outputs/flutter-apk/app-release.apk"
                    
                    // Alternative 2: Use findFiles from pipeline utility steps plugin
                    // (requires installing "Pipeline Utility Steps" plugin first)
                    // def apkFiles = findFiles(glob: '**/app-release.apk')
                    // def apkPath = apkFiles[0].path
                    
                    // Verify APK exists
                    sh "ls -la ${apkPath} || echo 'APK not found!'"
                    
                    // Upload to Artifactory
                    withCredentials([string(credentialsId: 'artifactory-token', variable: 'ARTIFACTORY_TOKEN')]) {
                        sh """
                            curl -H "Authorization: Bearer ${ARTIFACTORY_TOKEN}" \
                                 -X PUT "${ARTIFACTORY_URL}/artifactory/${ARTIFACTORY_REPO}/${env.BUILD_NUMBER}/app-release.apk" \
                                 -T ${apkPath}
                        """
                    }
                    
                    echo "APK published to Artifactory: ${ARTIFACTORY_URL}/artifactory/${ARTIFACTORY_REPO}/${env.BUILD_NUMBER}/app-release.apk"
                }
            }
        }
    }
}