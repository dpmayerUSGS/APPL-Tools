//----------------------------------------------------------------------------
// 
//                                UNCLASSIFIED
// 
//                     Copyright © 1989-2013 BAE Systems
//                            ALL RIGHTS RESERVED
// Use of this software product is governed by the terms of a license
// agreement. The license agreement is found in the installation directory.
//  
// The export of the information contained within this document is governed
// by the Export Administration Regulations (EAR) of the United States. This
// document may not be transferred to a non-U.S. person/entity without the
// proper prior authorization of the U.S. Government. Violations may result
// in administrative, civil or criminal penalties.
//  
//               For support, please visit http://www.baesystems.com/gxp
//----------------------------------------------------------------------------

//-------------------------------------------------
// Includes
#include "stdafx.h"

#include <errno.h>

//-------------------------------------------------
// Namespaces
using namespace GXP_API;
using namespace std;

//-------------------------------------------------
// Defined Constants
#define MAX_PATH_LENGTH 2048

//-------------------------------------------------
// OsUtil::StartApplication
pid_t
OsUtil::StartApplication(
   const char* application)
{
   if(!application || !strlen(application))
   {
      return false;
   }

   string exe = application;
   exe += ".exe";

   PROCESS_INFORMATION process_info;
   memset((void*)&process_info, 0, sizeof(PROCESS_INFORMATION));

   STARTUPINFO start_info;
   memset((void*)&start_info, 0, sizeof(STARTUPINFO));
   start_info.cb = sizeof(STARTUPINFO);

   if(CreateProcess(
      exe.c_str(),
      NULL,
      NULL,
      NULL,
      FALSE,
      NORMAL_PRIORITY_CLASS,
      NULL,
      NULL,
      &start_info,
      &process_info) == TRUE)
   {
      return 10;
   }

   cout << "REPORTED ERROR: " << (long)GetLastError() << endl;

   return 0;
}

//-------------------------------------------------
// OsUtil::StartGxpApplication
pid_t
OsUtil::StartGxpApplication()
{
   std::string gxp_path;
   const char* path = NULL;

   // The SOCETGXPEXE environment
   // variable must be set to the bin
   // directory of the SOCET GXP install.

   // This environment variable gets set by
   // the start_gxp.ksh and start_gxp.bat scripts.

   path = getenv("SOCETGXPEXE");

   if(!path)
   {
      cout << "SOCETGXPEXE is not set." << endl;
      return 0;
   }

   gxp_path = path;
   gxp_path += "\\SocetGxp";

   return StartApplication(gxp_path.c_str());
}

//-------------------------------------------------
// OsUtil::WaitOnProcess
void
OsUtil::WaitOnProcess(
   pid_t pid)
{
  // This function only makes sense in Unix environments

  return;
}

//-------------------------------------------------
// OsUtil::NormalizeLocalPath
string
OsUtil::NormalizeLocalPath(
   const char* path)
{
   string normalized_path;
   bool drive_set = false;

   if(!strlen(path))
      return normalized_path;

   char cur_path[MAX_PATH_LENGTH] = {'\0'};
   long max_path = MAX_PATH_LENGTH;

   if(strlen(path) > 3)
   {
      if(path[1] == ':' && path[2] == '\\')
         drive_set = true;
   }

   if(!drive_set)
   {
      if(_getcwd(cur_path, max_path) == NULL)
         return normalized_path;

      normalized_path = cur_path;
      normalized_path += '\\';
   }

   normalized_path += path;

   return normalized_path;
}

//-------------------------------------------------
// OsUtil::Sleep
void
OsUtil::Sleep(int seconds)
{
   // Sleep on windows is in milliseconds

   ::Sleep(seconds*1000);
}
