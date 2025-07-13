pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'
        WORKSPACE = '/var/lib/jenkins/.jenkins/workspace/flutter-hello-world_main'
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
    }
}