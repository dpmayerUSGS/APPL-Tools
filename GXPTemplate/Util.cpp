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

//-------------------------------------------------
// Namespaces
using namespace GXP_API;
using namespace std;

//-------------------------------------------------
// Util::checkStatus
bool
Util::checkStatus(
   GSIT_STATUS comm_status,
   const ApiStatus& gxp_status)
{
   ApiString error_string;
   bool success = false;

   streamsize ios_width = cout.width();
   char ios_fill = cout.fill();

   gxp_status.getErrorString(error_string);

   if(GSIT_FAILED(comm_status) || GSIT_FAILED(gxp_status.getErrorCode()))
   {
      streamsize ios_width = cout.width();
      char ios_fill = cout.fill();

      cout << " >> ERROR <<" << endl;

      cout << "Communication Error: 0x" << hex << setw(8) << setfill('0') << (long)comm_status << endl;
      cout << resetiosflags(ios_base::hex);

      cout << "GXP Error: 0x" << hex << setw(8) << setfill('0') << gxp_status.getErrorCode() << endl;
      cout << resetiosflags(ios_base::hex);

      if(error_string.getLength())
        cout << "GXP Error: " << error_string.getText() << endl;

      cout << endl << endl;

      cout.fill(ios_fill);
      cout.width(ios_width);   
   }
   
   success = GSIT_SUCCEEDED(comm_status) && GSIT_SUCCEEDED(gxp_status.getErrorCode());

   return success;
}
