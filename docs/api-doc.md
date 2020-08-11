will print api doc
## store
    takes two parameters in a POST: bucket and a file

    * bucket is one of the allowed bucket names
    * file is the file to archive, the filename is not used

    returns a list of data first OK or FAIL then:

    filename:%s;bucket:%s;date:%s;sha256:%s;uuid:%s
    
## get
    takes three parameters in the rest api: bucket, date and a filename
    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)
    * filename is the uuid(4) received by the server when storing files
    returns the file or FAIL
    
## hash
    takes three parameters in the rest api:

    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)
    * filename is the uuid(4) received by the server when storing files

    returns the hash of the file or FAIL
    
## list

    * if called with /<bucket>/<date>/ the available uuid:s is listed
    * if called with /<bucket>/ the available dates:s is listed
    * if called with / the available buckets:s is listed

    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)

    returns json string with findings
    
## delete
    delete must explicitly be allowed (default off) ,
    takes three parameters in the rest api:

    * bucket where the file was stored (one of the allowed bucket names)
    * date when the file was stored (has to be formated YYYY-MM-DD)
    * filename is the uuid(4) received by the server when storing files

    returns DELOK or DELFAIL and a string describing the file
    
## health

        takes one optional parameter in the rest api

        * verbose - returns more information about health status

        returns 200 ALLOK: date: <date> if all health checks is ok
        returns 403 ERROR date: <date> notallowed if ip not in
             ALLOWED_IPS_HEALTH
        returns 500 ERROR date: <date>: <description of error> if some error
        is found
    
