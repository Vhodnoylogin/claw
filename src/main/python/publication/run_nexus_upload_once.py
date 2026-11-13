"""One explicitly reviewed GitHub-runner recovery for accepted CLAW0.10.

Reuse cee8067's stdlib publisher, first-manual-run guard and public-asset
verification. The failed local attempt is retained, never replayed or resumed.
"""
from pathlib import Path
from urllib import request
from urllib.parse import urlparse
import argparse,hashlib,json,os,re,subprocess,sys
import nexus_upload_once as upload

ROOT=Path(__file__).resolve().parents[4]
SOURCE='1e7513b8c4e439ed93fec6d0856642b7cf90e75d'
ZIP_URL='https://github.com/Vhodnoylogin/claw/releases/download/claw/0.10.0/CLAW.-.Customizable.Lycanthrope.Appearance.and.Weight.zip'
GUIDE_URL='https://github.com/Vhodnoylogin/claw/releases/download/claw/0.10.0/CLAW-Modder-Guide.md'

def checked_pin(path,reviewed_sha=None):
    if reviewed_sha is not None:upload.require(upload.digest(path)==reviewed_sha,'Reviewed package pin changed')
    pin=upload.read(path)
    upload.require(type(pin['schemaVersion']) is int and pin['schemaVersion']==1 and pin['game']==upload.GAME and pin['globalModId']==upload.GLOBAL_MOD and pin['activeFileId']==upload.ACTIVE_FILE and pin['previousVersionId']==upload.PREVIOUS_VERSION and pin['scopedPreviousVersionId']==upload.SCOPED_PREVIOUS and pin['version']==upload.VERSION,'Unexpected fixed release target')
    upload.require(pin['sourceCommit']==SOURCE and pin['archive']['sha256']=='f571ad5e486600c3fcd06432034eeed9a2837be2706ca59bc0f72be28262c91a' and pin['archive']['bytes']==24362264 and pin['archive']['url']==ZIP_URL and pin['releaseDll']['sha256']=='ccf7718d90f99ebc176b4231566fa6cc1cbbb117741de6e1babe267ab508503b','Accepted archive/DLL/source changed')
    upload.require(pin['guide']['url']==GUIDE_URL and pin['guide']['sha256']=='9f694ba7d6303303b8ea93410ecb3fe8f32299c3f166a1185bfb0df83802fe4c' and pin['guide']['bytes']==14336,'Published guide identity changed')
    upload.require(pin['publisherSha256']==upload.digest(upload.__file__) and pin['runnerSha256']==upload.digest(__file__),'Reviewed publisher closure changed')
    upload.require(pin['requirements']=={'groups':8,'dlcGroups':0,'meaningSha256':'bd5f79eed7226b48bd35534bfc04576904d02f2a7035afc0b2adeb52c70afedd'},'Reviewed requirements changed')
    evidence=pin['acceptedEvidence']
    upload.require(evidence['fullReleaseAccepted'] is True and evidence['releaseAcceptanceSha256']=='82168251eb7e98c4abde349fccde1f5b7fed71b41b2a699e47a1c46e28f4442e' and evidence['runtimeRun']['id']=='20261113-132921-ea509a' and evidence['runtimeRun']['result']=='passed' and evidence['runtimeRun']['restored'] is True,'Root final acceptance unavailable')
    recovery=pin['transportRecovery']
    upload.require(type(pin['remoteRecoveryReady']) is bool and recovery['oldUploadId']==upload.OLD_UPLOAD_ID and recovery['oldState']=='created' and recovery['oldFinaliseOrVersionIntentAbsent'] is True and recovery['oldAttemptMustNotBeReplayed'] is True and recovery['claimedFieldAvailable'] is False,'Explicit old-attempt recovery basis changed')
    texts={}
    for key in ('description','modDescription','changelog'):
        relative=Path(pin[key]['path']);source=(ROOT/relative).resolve()
        upload.require(not relative.is_absolute() and source.is_relative_to(ROOT),'Publication source escapes repository')
        upload.require(upload.digest(source)==pin[key]['sourceLfSha256'],'Approved canonical Git publication bytes changed')
        texts[key]=source.read_text(encoding='utf-8').strip()
    baseline=pin['baselineModDescription']
    upload.require(hashlib.sha256(baseline['text'].encode()).hexdigest()==baseline['sourceLfSha256'],'Pinned description preimage bytes changed')
    texts['baselineModDescription']=baseline['text'].strip()
    upload.require(pin['changelog']['mode']=='append-once','One new changelog append required')
    old,new=texts['baselineModDescription'],texts['modDescription']
    ornaments=lambda s:re.findall(r'\[img[^]]*\].*?\[/img\]',s)
    upload.require(len(ornaments(old))==6 and ornaments(old)==ornaments(new),'Six ornaments changed')
    upload.require(old[old.index('Supported human bodies'):old.index('Requirements')]==new[new.index('Supported human bodies'):new.index('Requirements')],'Supported body lists changed')
    upload.require('Credits &amp; source' in old and old.split('Credits &amp; source')[-1]==new.split('Credits &amp; source')[-1],'Final credits changed')
    upload.require(hashlib.sha256(old.encode()).hexdigest()=='f09b81f87e60f40769ce213b960eb1b8ef2f970533a6c3ad78e1ce388fe4a7c6','Reviewed actual description preimage changed')
    return pin

def workflow_environment(env):
    upload.require(env.get('GITHUB_REPOSITORY')=='Vhodnoylogin/claw' and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and env.get('GITHUB_REF')=='refs/heads/main' and env.get('GITHUB_RUN_ATTEMPT')=='1' and env.get('GITHUB_RUN_NUMBER')=='1' and re.fullmatch(r'\d+',env.get('GITHUB_RUN_ID','')) and env.get('RUNNER_TEMP'),'Only first manual main workflow attempt admitted')
    return Path(env['RUNNER_TEMP']).resolve()/('claw-nexus-010-recovery-'+env['GITHUB_RUN_ID'])

def verify_committed_source(pin):
    def git(*args):
        result=subprocess.run(['git','-C',str(ROOT),*args],capture_output=True)
        upload.require(result.returncode==0,'Accepted Git source/tag unavailable')
        return result.stdout
    upload.require(git('rev-parse','HEAD').decode().strip()==os.environ.get('GITHUB_SHA'),'Runner checkout differs from dispatched infrastructure commit')
    upload.require(git('rev-parse','refs/tags/claw/0.10.0^{commit}').decode().strip()==SOURCE,'Public runtime tag changed')
    git('merge-base','--is-ancestor',SOURCE,'HEAD')
    for key in ('description','modDescription','changelog'):
        relative=pin[key]['path']
        upload.require(git('show',SOURCE+':'+relative)==(ROOT/relative).read_bytes(),'Publication text differs from accepted runtime commit')

class PublicAssetRedirect(request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parsed=urlparse(newurl)
        upload.require(parsed.scheme=='https' and parsed.username is None and parsed.password is None and type(parsed.hostname) is str and (parsed.hostname=='github.com' or parsed.hostname.endswith('.githubusercontent.com')),'Public asset redirected outside GitHub hosts')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download(pin,directory):
    asset=pin['archive'];upload.require(asset['url'] in {ZIP_URL,GUIDE_URL},'Unexpected public asset URL')
    filename=asset['filename']
    upload.require(type(filename) is str and Path(filename).name==filename and re.fullmatch(r"[a-zA-Z0-9 _'().-]+\.(?:zip|md)",filename) and not filename.startswith('.'),'Unsafe asset basename')
    destination=directory/filename;opener=request.build_opener(PublicAssetRedirect())
    with opener.open(asset['url'],timeout=60) as response,destination.open('xb') as stream:
        count=0
        while chunk:=response.read(1024*1024):
            count+=len(chunk);upload.require(count<=asset['bytes'],'Public asset exceeds accepted size');stream.write(chunk)
    upload.require(count==asset['bytes'] and upload.digest(destination)==asset['sha256'],'Downloaded public asset hash/size mismatch')
    return destination

def run(pin_path,reviewed_sha):
    pin=checked_pin(pin_path,reviewed_sha)
    upload.require(pin['remoteRecoveryReady'] is True,'Remote recovery remains disabled pending independent/root review')
    directory=workflow_environment(os.environ);verify_committed_source(pin)
    directory.mkdir(exist_ok=False)
    upload.durable(directory/'run-intent.json',{'pinSha256':reviewed_sha,'oldUploadId':upload.OLD_UPLOAD_ID,'policy':'One new reviewed remote allocation; never replay old local attempt or this workflow'})
    try:
        archive=download(pin,directory);download({'archive':pin['guide']},directory)
        accepted={'schemaVersion':1,'fullReleaseAccepted':True,'sourceCommit':SOURCE,'releaseArchive':pin['archive'],'releaseDll':pin['releaseDll'],'acceptedEvidence':pin['acceptedEvidence']}
        acceptance_path=directory/'accepted-package.json';upload.durable(acceptance_path,accepted)
        api=upload.Api()
        old=api.call('GET','/uploads/'+upload.OLD_UPLOAD_ID)
        upload.require(old['id']==upload.OLD_UPLOAD_ID and old['state']=='created','Old upload is no longer unfinalised; no new allocation')
        dependencies=api.call('GET','/mod-file-versions/'+upload.PREVIOUS_VERSION+'/dependencies');meaning=upload.dependency_meaning(dependencies)
        upload.require(len(meaning['ranges'])==8 and len(meaning['dlc'])==0 and hashlib.sha256(upload.canonical(meaning).encode()).hexdigest()==pin['requirements']['meaningSha256'],'Reviewed inherited requirements changed')
        requirements_path=directory/'previous-dependencies.json';upload.durable(requirements_path,dependencies)
        value={key:pin[key] for key in ('schemaVersion','game','globalModId','activeFileId','previousVersionId','scopedPreviousVersionId','version','name','sourceCommit','allowedStorageHosts')}
        value.update(publicationReady=True,helperSha256=upload.digest(upload.__file__),receiptDirectory=str(directory/'attempt'),archive={**pin['archive'],'path':str(archive)},acceptance={'path':str(acceptance_path),'sha256':upload.digest(acceptance_path)},requirementsSnapshot={'path':str(requirements_path),'sha256':upload.digest(requirements_path)})
        for key in ('description','modDescription','changelog'):
            source=ROOT/pin[key]['path'];value[key]={**pin[key],'path':str(source),'sha256':upload.digest(source)}
        baseline_path=directory/'baseline-mod-description.txt'
        with baseline_path.open('xb') as stream:stream.write(pin['baselineModDescription']['text'].encode())
        value['baselineModDescription']={'path':str(baseline_path),'sha256':upload.digest(baseline_path)}
        proposal_path=directory/'proposal.json';upload.durable(proposal_path,value)
        value,accepted=upload.proposal(proposal_path);upload.publish(value,accepted,proposal_path)
        result=upload.read(directory/'attempt/upload-result.json')
        upload.durable(directory/'run-summary.json',{'uploaded':True,'fileId':result['fileId'],'versionId':result['versionId'],'archiveSha256':result['archiveSha256'],'sourceCommit':SOURCE,'requirementsPreserved':result['requirementsPreserved'],'publicDownloadReady':result['publicDownloadReady'],'changelogAppendedOnce':result['changelogAppendedOnce'],'descriptionReadbackMatched':result['descriptionReadbackMatched'],'oldLocalAttemptReplayed':False,'temporarySecretRemovalRequired':True})
    except BaseException as error:
        upload.durable(directory/'run-summary.json',{'uploaded':False,'doNotReplay':True,'errorType':type(error).__name__,'reason':str(error) if isinstance(error,upload.SafeStop) else 'Sensitive transport details omitted','oldLocalAttemptReplayed':False,'temporarySecretRemovalRequired':True})
        raise upload.SafeStop('Remote one-use recovery stopped; inspect receipts without replay') from None

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--pin',type=Path,required=True);parser.add_argument('--reviewed-pin-sha256');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if args.apply:
        upload.require(args.reviewed_pin_sha256 is not None,'Exact reviewed pin SHA required');run(args.pin,args.reviewed_pin_sha256)
    else:
        pin=checked_pin(args.pin);print(json.dumps({'networkUsed':False,'credentialRead':False,'remoteRecoveryReady':pin['remoteRecoveryReady'],'archiveSha256':pin['archive']['sha256'],'pinSha256':upload.digest(args.pin),'requirementsGroups':8}))

if __name__=='__main__':
    try:main()
    except upload.SafeStop as error:
        print(json.dumps({'stopped':True,'reason':str(error)}),file=sys.stderr);raise SystemExit(1) from None
