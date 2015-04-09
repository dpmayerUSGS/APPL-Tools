// GXPTemplate.cpp : Defines the entry point for the console application.
//

#include "stdafx.h"

//Defined Constants
#define MAX_CONNECT_ATTEMPTS 100 // maximum number of launch GXP attempts

//Namespaces
using namespace GXP_API;
using namespace std;

//Prototype
void exec();  //Define args to exec if necessary

int _tmain(int argc, _TCHAR* argv[])
{
	ApiManager::InitializeApi();

	//Main
	exec();

	ApiManager::UninitializeApi();
	return 0;
}

void exec()
{
	ApiManager gxp_manager;
	ApiStatus status;
	GSIT_STATUS comm_status = GSIT_FAILURE;

	//Connect to GXP
	comm_status = gxp_manager.gxpConnect(status);


	//Disconnect from GXP
	gxp_manager.gxpDisconnect();
};
