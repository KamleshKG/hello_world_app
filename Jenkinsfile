pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'
        WORKSPACE = '/var/lib/jenkins/.jenkins/workspace/flutter-hello-world_main'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io'
        ARTIFACTORY_REPO = 'flutter-app-releases-generic-local'
        ARTIFACTORY_CREDS = credentials('artifactory-token') // Store your token in Jenkins credentials
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
                    // Find the built APK file
                    def apkFile = findFiles(glob: 'build/app/outputs/flutter-apk/app-release.apk')[0].path
                    
                    // Upload to Artifactory
                    withCredentials([string(credentialsId: 'artifactory-credentials', variable: 'ARTIFACTORY_TOKEN')]) {
                        sh """
                            curl -H "Authorization: Bearer ${ARTIFACTORY_TOKEN}" \
                                 -X PUT "${ARTIFACTORY_URL}/artifactory/${ARTIFACTORY_REPO}/${env.BUILD_NUMBER}/app-release.apk" \
                                 -T ${apkFile}
                        """
                    }
                    
                    echo "APK published to Artifactory: ${ARTIFACTORY_URL}/artifactory/${ARTIFACTORY_REPO}/${env.BUILD_NUMBER}/app-release.apk"
                }
            }
        }
    }
		
  }
	
	
