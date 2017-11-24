#Author : Pavani Boga ( pavanianapala@gmail.com )
#Date : 11/13/2017
#Job : https://www.upwork.com/jobs/~011377399ad82c874a
# This script reporders the playlists in the master playlist file which is in S3

import boto3
import m3u8
import os

bucket = 'gamesense-videos-hls'
s3_url = 'https://s3.amazonaws.com'

s3_client = boto3.client('s3')
paginator = s3_client.get_paginator('list_objects_v2')
params = { 'Bucket' : bucket, 'Delimiter' : '/', 'StartAfter': 'M17-23b2' }
page_iterator = paginator.paginate(**params)

for page in page_iterator:
    try:
        for dir in page['CommonPrefixes']:
            for entry in s3_client.list_objects_v2(Bucket=bucket,Prefix=dir['Prefix'])['Contents']:
                if 'master.m3u8' in entry['Key']:
                    if not os.path.exists('/tmp/test/%s' %dir['Prefix']):
                        os.makedirs('/tmp/test/%s' %dir['Prefix'])
                    new_m3u8 = m3u8.M3U8()
                    sort_order = [ 4, 6, 5, 3, 2, 1, 0 ]
                    stream = m3u8.load('/'.join([s3_url,bucket,entry['Key']]))
                    for idx in sort_order:
                        new_m3u8.add_playlist(stream.playlists[idx])
                    new_m3u8.dump('/tmp/test/%s' %entry['Key'])
                    s3_client.upload_file('/tmp/test/%s' %entry['Key'],'gamesense-videos-hls', entry['Key'])
                    print('------Done with %s----------' %entry['Key'])
                    
    except KeyError:
        pass  
